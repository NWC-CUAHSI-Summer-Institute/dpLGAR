from typing import Dict, Optional, Callable

from omegaconf import DictConfig
import torch
import torch.nn as nn

from dpLGAR.lgar.soil_column.base_state import BaseState
from dpLGAR.lgar.layers.Layer import Layer


class BaseModel(nn.Module):
    """Abstract base model class, don't use this class for model training.

    Parameters
    ----------
    cfg : Config
        The run configuration.
    """

    def __init__(self, cfg: DictConfig):
        super(BaseModel, self).__init__()
        self.cfg = cfg

        self.alpha = torch.tensor(0.0)
        self.n = torch.tensor(0.0)
        self.ksat = torch.tensor(0.0)
        self.theta_e = {}
        self.theta_r = {}
        self.ponded_depth_max = torch.tensor(0.0)

        self.top_layer = None
        self.bottom_layer = None
        self.num_wetting_fronts = None
        self.wf_free_drainage_demand = None

        self.soil_state = None

        self.cfg.data.soil_index = {
            "theta_r": 0,
            "theta_e": 1,
            "theta_wp": 2,
            "theta_init": 3,
            "m": 4,
            "bc_lambda": 5,
            "bc_psib_cm": 6,
            "h_min_cm": 7,
            "alpha": 8,
            "n": 9,
        }

        self._read_attributes()
        self._set_parameters()
        self._create_soil_profile()
        self._create_local_mass_balance()
        self._create_global_mass_balance()


    def _create_global_mass_balance(self):
        """Creates the local mass balance parameters"""
        raise NotImplementedError

    def _create_local_mass_balance(self):
        """Creates the local mass balance parameters"""
        raise NotImplementedError

    def _create_soil_profile(self):
        """Creates the soil state and soil layers"""
        self.soil_state = self._create_soil_state()
        layer_index = 0  # This is the top layer
        self.top_layer = Layer(
            self.global_params,
            layer_index,
            self.c,
            self.ksat,
            self.rank,
        )
        self.bottom_layer = self.top_layer
        while self.bottom_layer.next_layer is not None:
            self.bottom_layer = self.bottom_layer.next_layer

    def _create_soil_state(self):
        """Defines all global soil parameters"""
        return BaseState(self.cfg, self.ponded_depth_max)

    def _set_parameters(self):
        """Sets the module parameters"""
        raise NotImplementedError

    def forward(self, i, x) -> (torch.Tensor, torch.Tensor):
        """Perform a forward pass.

        Parameters
        ----------
        data : Dict[str, torch.Tensor]
            Dictionary, containing input features as key-value pairs.

        Returns
        -------
        torch.Tensor
            Model output and potentially any intermediate states and activations as a dictionary.
        """
        raise NotImplementedError
