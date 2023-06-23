"""A file to store the function where we read the input data"""
import logging

from omegaconf import DictConfig
import numpy as np
import pandas as pd
from pathlib import Path
import torch

from src.physics.LGAR.utils import (
    calc_theta_from_h,
    calc_bc_lambda_psib_cm,
    calc_h_min_cm,
)
from src.tests.sanity_checks import DataError

log = logging.getLogger("data.read_forcing")
torch.set_default_dtype(torch.float64)


def read_forcing_data(cfg: DictConfig) -> (np.ndarray, torch.Tensor, torch.Tensor):
    """
    a function to read the forcing input dataset
    :param file_path: the file we want to read
    :return:
    - time
    - precipitation
    - PET
    """
    forcing_file_path = Path(cfg.data.forcing_file)
    device = cfg.device

    # Check if forcing file exists
    if not forcing_file_path.is_file():
        log.error(f"File {forcing_file_path} doesn't exist")
        raise DataError
    df = pd.read_csv(forcing_file_path)

    # Convert pandas dataframe to PyTorch tensors
    time = df["Time"].values
    precip = torch.tensor(df["P(mm/h)"].values, dtype=torch.float64, device=device)
    pet = torch.tensor(df["PET(mm/h)"].values, dtype=torch.float64, device=device)

    return time, precip, pet


def read_soils_file(
    cfg: DictConfig, wilting_point_psi_cm: torch.Tensor
) -> pd.DataFrame:
    """
    Reading the soils dataframe
    :param cfg: the config file
    :param wilting_point_psi_cm wilting point (the amount of water not available for plants or not accessible by plants)

    Below are the variables used inside of the soils dataframe:
    Texture: The soil classification
    theta_r: Residual Water Content
    theta_e: Wilting Point
    alpha(cm^-1): ???"
    n: ???
    m: ???
    Ks(cm/h): Saturated Hydraulic Conductivity

    :return:
    """
    device = cfg.device
    soils_file_path = Path(cfg.data.soil_params_file)

    # Check if forcing file exists
    if not soils_file_path.is_file():
        log.error(f"File {soils_file_path} doesn't exist")
        raise DataError

    # Checking the file extension so we correctly read the file
    if soils_file_path.suffix == ".csv":
        df = pd.read_csv(soils_file_path)
    elif soils_file_path.suffix == ".dat":
        df = pd.read_csv(soils_file_path, delimiter=r"\s+", engine="python")
    else:
        log.error(f"File {soils_file_path} has an invalid type")
        raise DataError

    df["theta_wp"] = calc_theta_from_h(wilting_point_psi_cm, df, device)
    df = calc_bc_lambda_psib_cm(df, device)
    df = calc_h_min_cm(df, device)
    return df
