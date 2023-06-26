from omegaconf import DictConfig
import logging
import numpy as np
import torch
from torch import Tensor

from lgartorch.models.physics.utils import (
    calc_theta_from_h,
    calc_se_from_theta,
    calc_h_from_se,
)

log = logging.getLogger("models.physics.lgar.aet")


def calculate_aet(global_params, pet, psi_cm, theta_e, theta_r, m, alpha, n) -> Tensor:
    """
    /* authors : Fred Ogden and Ahmad Jan
    Translated by Tadd Bindas to Python
    year    : 2022
    the code computes actual evapotranspiration given PET.
    It uses an S-shaped function used in HYDRUS-1D (Simunek & Sejna, 2018).
    AET = PET * 1/(1 + (h/h_50) )^3
    h is the capillary head at the surface and
    h_50 is the capillary head at which AET = 0.5 * PET. */
    :param global_params:
    :param pet: potential evapotranspiration
    :param theta_e: ????
    :param theta_r: ????
    :param m: Van Genuchten
    :param alpha:
    :param n:
    :return: actual evapotransporation
    """
    theta_fc = (
        theta_e - theta_r
    ) * global_params.relative_moisture_at_which_PET_equals_AET + theta_r
    wp_head_theta = calc_theta_from_h(
        global_params.wilting_point_psi_cm, alpha, n, m, theta_e, theta_r
    )
    theta_wp = (theta_fc - wp_head_theta) * 0.5 + wp_head_theta  # theta_50 in python
    se = calc_se_from_theta(theta_wp, theta_e, theta_r)
    psi_wp_cm = calc_h_from_se(se, alpha, m, n)

    h_ratio = 1.0 + torch.pow((psi_cm / psi_wp_cm), 3.0)
    actual_ET_demand_ = pet * (1 / h_ratio)
    # Actual ET cannot be higher than PET nor negative
    actual_ET_demand = torch.clamp(actual_ET_demand_, min=0.0, max=pet)
    return actual_ET_demand
