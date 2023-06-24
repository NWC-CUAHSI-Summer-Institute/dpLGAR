import logging
from omegaconf import DictConfig
import time
import torch
from torch import Tensor
from torch.utils.data import DataLoader

from lgartorch.agents.base import BaseAgent
from lgartorch.data.Data import Data
from lgartorch.data.metrics import calculate_nse
from lgartorch.models.dpLGAR import dpLGAR

log = logging.getLogger("agents.DifferentiableLGAR")


class DifferentiableLGAR(BaseAgent):
    def __init__(self, cfg: DictConfig) -> None:
        """
        Initialize the Differentiable LGAR code

        Sets up the initial state of the agent
        :param cfg:
        """
        super().__init__()

        # Setting the cfg object and manual seed for reproducibility
        self.cfg = cfg
        torch.manual_seed(0)
        torch.set_default_dtype(torch.float64)

        self.cfg.models.endtime_s = (
            self.cfg.models.endtime * self.cfg.conversions.hr_to_sec
        )
        self.cfg.models.forcing_resolution_h = (
            self.cfg.models.forcing_resolution / self.cfg.conversions.hr_to_sec
        )
        self.cfg.models.time_per_step = (
            self.cfg.models.forcing_resolution_h * self.cfg.conversions.hr_to_sec
        )
        self.cfg.models.nsteps = int(
            self.cfg.models.endtime_s / self.cfg.models.time_per_step
        )

        self.model = dpLGAR(self.cfg)

        self.data = Data(cfg, self.model.alpha, self.model.n, self.model.ksat)
        self.data_loader = DataLoader(self.data, batch_size=1, shuffle=False)

        self.criterion = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=cfg.models.hyperparameters.learning_rate
        )

        self.current_epoch = 0

    def run(self):
        """
        The main operator
        :return:
        """
        try:
            self.train()
        except KeyboardInterrupt:
            log.info("You have entered CTRL+C.. Wait to finalize")

    def train(self):
        """
        Main training loop
        :return:
        """
        self.model.train()
        for epoch in range(1, self.cfg.models.hyperparameters.epochs + 1):
            self.train_one_epoch()
            self.current_epoch += 1

    def train_one_epoch(self):
        """
        One epoch of training
        :return:
        """
        i = 0
        for x, y_t in self.data_loader:
            self.optimizer.zero_grad()
            y_hat = self.model(x, self.data.c)
            self.validate(y_hat, y_t)
            i += 1

    def validate(self, y_hat_: Tensor, y_t_: Tensor) -> None:
        """
        One cycle of model validation
        This function calculates the loss for the given predicted and actual values,
        backpropagates the error, and updates the model parameters.

        Parameters:
        - y_hat_ : The tensor containing predicted values
        - y_t_ : The tensor containing actual values.
        """
        warmup = self.cfg.data.hyperparameters.warmup
        y_hat = y_hat_[warmup:]
        y_t = y_t_[warmup:]

        # Outputting trained Nash-Sutcliffe efficiency (NSE) coefficient
        log.info(
            f"trained NSE: {calculate_nse(y_hat.detach().squeeze().numpy(), y_t.detach().squeeze().numpy()):.4}"
        )

        # Compute the overall loss
        loss = self.criterion(y_hat, y_t)

        # Backpropagate the error
        start = time.perf_counter()
        loss.backward()
        end = time.perf_counter()

        # Log the time taken for backpropagation and the calculated loss
        log.debug(f"Back prop took : {(end - start):.6f} seconds")
        log.debug(f"Loss: {loss}")

        # Update the model parameters
        self.optimizer.step()


    def finalize(self):
        """
        Finalizes all the operations of the 2 Main classes of the process, the operator and the data loader
        :return:
        """
        raise NotImplementedError

    def load_checkpoint(self, file_name):
        """
        Latest checkpoint loader
        :param file_name: name of the checkpoint file
        :return:
        """
        raise NotImplementedError

    def save_checkpoint(self, file_name="checkpoint.pth.tar", is_best=0):
        """
        Checkpoint saver
        :param file_name: name of the checkpoint file
        :param is_best: boolean flag to indicate whether current checkpoint's metric is the best so far
        :return:
        """
        raise NotImplementedError
