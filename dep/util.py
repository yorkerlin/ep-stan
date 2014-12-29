""" Utilities for the distributed EP algorithm.

The most recent version of the code can be found on GitHub:
https://github.com/gelman/ep-stan

"""

# Licensed under the 3-clause BSD license.
# http://opensource.org/licenses/BSD-3-Clause
#
# Copyright (C) 2014 Tuomas Sivula
# All rights reserved.

from __future__ import division
import os
import pickle
import numpy as np
from scipy import linalg
import matplotlib.pyplot as plt
from pystan import StanModel

from cython_util import copy_triu_to_tril

# LAPACK positive definite inverse routine
dpotri_routine = linalg.get_lapack_funcs('potri')


def compare_plot(a, b, a_err=None, b_err=None, a_label=None, b_label=None):
    """Compare values of a in the ones in b."""
    
    a = np.asarray(a)
    b = np.asarray(b)
    
    fig = plt.figure()
    ax = plt.plot(b, a, 'bo')[0].get_axes()
    limits = (min(ax.get_xlim()[0], ax.get_ylim()[0]),
              max(ax.get_xlim()[1], ax.get_ylim()[1]))
    ax.set_xlim(limits)
    ax.set_ylim(limits)
    if not a_err is None:
        a_err = np.asarray(a_err)
        if len(a_err.shape) == 2:
            a_p = a_err[0]
            a_m = a_err[1]
        else:
            a_p = a_err
            a_m = a_err
        ax.plot(np.tile(b, (2,1)), np.vstack((a+a_p, a-a_m)), 'b-')
    if not b_err is None:
        b_err = np.asarray(b_err)
        if len(b_err.shape) == 2:
            b_p = b_err[0]
            b_m = b_err[1]
        else:
            b_p = b_err
            b_m = b_err
        ax.plot(np.vstack((b+b_p, b-b_m)), np.tile(a, (2,1)), 'b-')
    ax.plot(limits, limits, 'r-')
    if not a_label is None:
        ax.set_ylabel(a_label)
    if not b_label is None:
        ax.set_xlabel(b_label)
    
    return fig


def invert_normal_params(A, b=None, out_A=None, out_b=None, cho_form=False):
    """Invert moment parameters into natural parameters or vice versa.
    
    Switch between moment parameters (S,m) and natural parameters (Q,r) of
    a multivariate normal distribution. Providing (S,m) yields (Q,r) and vice
    versa.
    
    Parameters
    ----------
    A : ndarray
        A symmetric positive-definite matrix to be inverted. Either the
        covariance matrix S or the precision matrix Q.
    
    b : {None, ndarray}, optional
        The mean vector m, the natural parameter vector r, or None (default)
        if `out_b` is not requested.
    
    out_A, out_b : {None, ndarray, 'in_place'}, optional
        Spesifies where the output is calculate into; None (default) indicates
        that a new array is created, providing a string 'in_place' overwrites
        the corresponding input array.
    
    cho_form : bool
        If True, `A` is assumed to be the upper Cholesky of the real S or Q.
    
    Returns
    -------
    out_A, out_b : ndarray
        The corresponding output arrays (`out_A` in F-order). If `b` was not
        provided, `out_b` is None.
    
    Raises
    ------
    LinAlgError
        If the provided array A is not positive definite.
    
    """
    # Process parameters
    if out_A == 'in_place':
        out_A = A
    elif out_A is None:
        out_A = A.copy(order='F')
    else:
        np.copyto(out_A, A)
    if not out_A.flags.farray:
        # Convert from C-order to F-order by transposing (note symmetric)
        out_A = out_A.T
        if not out_A.flags.farray:
            raise ValueError('Provided array A is inappropriate')
    if not b is None:
        if out_b == 'in_place':
            out_b = b
        elif out_b is None:
            out_b = b.copy()
        else:
            np.copyto(out_b, b)
    else:
        out_b = None
    
    # Invert
    if not cho_form:
        cho = linalg.cho_factor(out_A, overwrite_a=True)
    else:
        # Already in upper Cholesky form
        cho = (out_A, False)
    if not out_b is None:
        linalg.cho_solve(cho, out_b, overwrite_b=True)
    _, info = dpotri_routine(out_A, overwrite_c=True)
    if info:
        # This should never occour if cho_factor was succesful ... I think
        raise linalg.LinAlgError(
                "dpotri LAPACK routine failed with error code {}".format(info))
    # Copy the upper triangular into the bottom
    copy_triu_to_tril(out_A)
    return out_A, out_b


def get_last_sample(fit, out=None):
    """Extract the last sample from a PyStan fit object.
    
    Parameters
    ----------
    fit :  StanFit4<model_name>
        Instance containing the fitted results.
    out : list of dict, optional
        The list into which the output is placed. By default a new list is
        created. Must be of appropriate shape and content (see Returns).
	    
	Returns
	-------
	list of dict
		List of nchains dicts for which each parameter name yields an ndarray
        corresponding to the sample values (similary to the init argument for
        the method StanModel.sampling).
    
    """
    
    # The following works at least for pystan version 2.5.0.0
    if not out:
        # Initialise list of dicts
        out = [{fit.model_pars[i] : np.empty(fit.par_dims[i], order='F')
                for i in range(len(fit.model_pars))} 
               for _ in range(fit.sim['chains'])]
    # Extract the sample for each chain and parameter
    for c in range(fit.sim['chains']):         # For each chain
        for i in range(len(fit.model_pars)):   # For each parameter
            p = fit.model_pars[i]
            if not fit.par_dims[i]:
                # Zero dimensional (scalar) parameter
                out[c][p][()] = fit.sim['samples'][c]['chains'][p][-1]
            elif len(fit.par_dims[i]) == 1:
                # One dimensional (vector) parameter
                for d in xrange(fit.par_dims[i][0]):
                    out[c][p][d] = fit.sim['samples'][c]['chains'] \
                                   [u'{}[{}]'.format(p,d)][-1]
            else:
                # Multidimensional parameter
                namefield = p + u'[{}' + u',{}'*(len(fit.par_dims[i])-1) + u']'
                it = np.nditer(out[c][p], flags=['multi_index'],
                               op_flags=['writeonly'], order='F')
                while not it.finished:
                    it[0] = fit.sim['samples'][c]['chains'] \
                            [namefield.format(*it.multi_index)][-1]
                    it.iternext()
    return out


def load_stan(filename, overwrite=False):
    """Load or compile a stan model.
    
    Parameters
    ----------
    filename : string
        The name of the model file. It may or may not contain path and ending
        '.stan' or '.pkl'. If a respective file with ending '.pkl' is found,
        the model is not built but loaded from the pickle file (unless
        `overwrite` is True). Otherwise the model is compiled from the
        respective file ending with '.stan' and saved into '.pkl' file.
    overwrite : bool
        Compile and save a new model even if a pickled model with same name
        already exists.
    
    """
    # Remove '.pkl' or '.stan' endings
    if filename.endswith('.pkl'):
        filename = filename[:-4]
    elif filename.endswith('.stan'):
        filename = filename[:-5]
    
    if not overwrite and os.path.isfile(filename+'.pkl'):
        # Use precompiled model
        with open(filename+'.pkl', 'rb') as f:
            sm = pickle.load(f)
    elif os.path.isfile(filename+'.stan'):
        # Compiling and save the model
        if not overwrite:
            print "Precompiled stan model {} not found.".format(filename+'.pkl')
            print "Compiling and saving the model."
        else:
            print "Compiling and saving the model {}.".format(filename+'.pkl')
        if '/' in filename:
            model_name = filename.split('/')[-1]
        elif '\\' in filename:
            model_name = filename.split('\\')[-1]
        else:
            model_name = filename
        sm = StanModel(file=filename+'.stan', model_name=model_name)
        with open(filename+'.pkl', 'wb') as f:
            pickle.dump(sm, f)
        print "Compiling and saving done."
    else:
        raise IOError("File {} or {} not found"
                      .format(filename+'.stan', filename+'.pkl'))
    return sm


# >>> Temp solution to suppres output from STAN model (remove when fixed)
# This part of the code is by jeremiahbuddha from:
# http://stackoverflow.com/questions/11130156/suppress-stdout-stderr-print-from-python-functions
class suppress_stdout(object):
    '''
    A context manager for doing a "deep suppression" of stdout and stderr in 
    Python, i.e. will suppress all print, even if the print originates in a 
    compiled C/Fortran sub-function.
       This will not suppress raised exceptions, since exceptions are printed
    to stderr just before a script exits, and after the context manager has
    exited (at least, I think that is why it lets exceptions through).      

    '''
    def __init__(self):
        # Open a pair of null files
        self.null_fds =  [os.open(os.devnull,os.O_RDWR) for x in range(2)]
        # Save the actual stdout (1) and stderr (2) file descriptors.
        self.save_fds = (os.dup(1), os.dup(2))

    def __enter__(self):
        # Assign the null pointers to stdout and stderr.
        os.dup2(self.null_fds[0],1)
        os.dup2(self.null_fds[1],2)

    def __exit__(self, *_):
        # Re-assign the real stdout/stderr back to (1) and (2)
        os.dup2(self.save_fds[0],1)
        os.dup2(self.save_fds[1],2)
        # Close the null files
        os.close(self.null_fds[0])
        os.close(self.null_fds[1])
# <<< Temp solution to suppres output from STAN model (remove when fixed)


