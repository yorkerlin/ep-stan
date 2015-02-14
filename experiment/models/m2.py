"""A simulated experiment model used by the sckript fit.py

Model name: m2
Definition:
    group index j = 1 ... J
    input index d = 1 ... D
    explanatory variable x = [x_1 ... x_D]
    response variable y
    local parameter alpha = [alpha_1 ... alpha_J]
    shared parameter beta = [beta_1 ... beta_D]
    shared parameter sigma_a
    shared parameter sigma_b
    y ~ bernoulli_logit(alpha_j + beta' * x)
    alpha ~ N(0, sigma_a)
    beta_d ~ N(0, sigma_b), for all d
    sigma_a ~ log-N(0, sigma_aH)
    sigma_b ~ log-N(0, sigma_bH)
    phi = [log(sigma_a), log(sigma_b)]

"""

# Licensed under the 3-clause BSD license.
# http://opensource.org/licenses/BSD-3-Clause
#
# Copyright (C) 2014 Tuomas Sivula
# All rights reserved.

from __future__ import division
import numpy as np


# ------------------------------------------------------------------------------
# >>>>>>>>>>>>> Configurations start >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# ------------------------------------------------------------------------------

# ====== Model parameters ======================================================
# If SIGMA_A is None, it is sampled from log-N(0,SIGMA_AH)
SIGMA_A = 2
SIGMA_AH = None
# If SIGMA_B is None, it is sampled from log-N(0,SIGMA_BH)
SIGMA_B = 1
SIGMA_BH = None

# ====== Prior =================================================================
# Prior for log(sigma_a)
M0_A = 0
V0_A = 1**2
# Prior for log(sigma_b)
M0_B = 0
V0_B = 1**2

# ------------------------------------------------------------------------------
# <<<<<<<<<<<<< Configurations end <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ------------------------------------------------------------------------------


def simulate_data(J, D, NPG, seed=None):
    """Simulate data from the model.
    
    Parameters
    ----------
    J : int
        Number of groups
    
    D : int
        Number of inputs
    
    NPG : {int, seq of ints}
        Number of observations per group (constant or [min, max])
    
    seed : int
        Seed for the presudo random generator
    
    Returns
    -------
    X : ndarray
        Explanatory variable
    
    y : ndarray
        Response variable data
    
    Nj : ndarray
        Number of observations in each group
    
    j_ind : ndarray
        The group index of each observation
    
    true_values : dict
        True values of `phi` and other inferred variables
    
    """
    
    # Set seed
    rnd_data = np.random.RandomState(seed=seed)
    
    # Parameters
    # Number of observations for each group
    if hasattr(NPG, '__getitem__') and len(NPG) == 2:
        Nj = rnd_data.randint(NPG[0],NPG[1]+1, size=J)
    else:
        Nj = NPG*np.ones(J, dtype=np.int64)
    # Total number of observations
    N = np.sum(Nj)
    # Observation index limits for J groups
    j_lim = np.concatenate(([0], np.cumsum(Nj)))
    # Group indices for each sample
    j_ind = np.empty(N, dtype=np.int64)
    for j in xrange(J):
        j_ind[j_lim[j]:j_lim[j+1]] = j
    
    # Assign parameters
    if SIGMA_A is None:
        sigma_a = np.exp(rnd_data.randn()*SIGMA_AH)
    else:
        sigma_a = SIGMA_A
    if SIGMA_B is None:
        sigma_b = np.exp(rnd_data.randn()*SIGMA_BH)
    else:
        sigma_b = SIGMA_B
    alpha_j = rnd_data.randn(J)*sigma_a
    beta = rnd_data.randn(D)*sigma_b
    phi_true = np.append(np.log(sigma_a), np.log(sigma_b))
    dphi = 2  # Number of shared parameters
    
    # Simulate data
    X = rnd_data.randn(N,D)
    y = alpha_j[j_ind] + X.dot(beta)
    y = 1/(1+np.exp(-y))
    y = (rnd_data.rand(N) < y).astype(int)
    
    return X, y, Nj, j_ind, {'phi':phi_true, 'alpha':alpha_j, 'beta':beta}


def get_prior(J, D):
    """Get prior for the model.
    
    Returns: S, m, Q, r
    """
    # Moment parameters of the prior (transposed in order to get F-contiguous)
    S0 = np.diag(np.append(V0_A, V0_B)).T
    m0 = np.append(M0_A, M0_B)
    # Natural parameters of the prior
    Q0 = np.diag(np.append(1./V0_A, 1./V0_B)).T
    r0 = np.append(M0_A/V0_A, M0_B/V0_B)
    return S0, m0, Q0, r0


def get_param_definitions(J, D):
    """Return the definition of the inferred parameters.
    
    Returns
    -------
    names : seq of str
        Names of the parameters
    
    shapes : seq of tuples
        Shapes of the parameters
    
    hiers : seq of int 
        The indexes of the hierarchical dimension of the parameter or None if it
        does not have one.
    
    """    
    names = ('alpha', 'beta')
    shapes = ((J,), (D,))
    hiers = (0, None)
    return names, shapes, hiers

