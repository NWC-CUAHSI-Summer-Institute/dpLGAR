"""a file to define the LGARBMI class"""
from bmipy import Bmi
import logging
from omegaconf import OmegaConf, DictConfig
import time
import torch
from tqdm import tqdm
from typing import Tuple

from src.data.read import read_forcing_data
from src.physics.Lgar import LGAR

log = logging.getLogger("LGARBmi")


class LGARBmi(Bmi):
    """The LGAR BMI class"""

    _name = "LGAR Torch"
    _input_var_names = (
        "precipitation_rate",
        "potential_evapotranspiration_rate",
        "soil_moisture_wetting_fronts",
        "soil_depth_wetting_fronts"
    )
    _output_var_names = (
        "precipitation",  # cumulative amount of precip
        "potential_evapotranspiration",  # cumulative amount of potential ET
        "actual_evapotranspiration",  # cumulative amount of actual ET
        "surface_runoff",  # direct surface runoff
        "giuh_runoff",
        "soil_storage",
        "total_discharge",
        "infiltration",
        "percolation",
        "groundwater_to_stream_recharge",
        "mass_balance",
    )

    def __init__(self):
        super().__init__()
        self._model = None
        self.device = None
        self._values = {}
        self._var_units = {}
        self._var_loc = "node"
        self._var_grid_id = 0
        self._grid_type = {}

        self._start_time = 0.0
        self._end_time = None
        self.timestep = None
        self._time_units = "s"

    def initialize(self, config_file: str) -> None:
        """Perform startup tasks for the model.

        Perform all tasks that take place before entering the model's time
        loop, including opening files and initializing the model state. Model
        inputs are read from a text-based configuration file, specified by
        `config_file`.

        Parameters
        ----------
        config_file : str
            The path to the model configuration file.

        Notes
        -----
        Models should be refactored, if necessary, to use a
        configuration file. CSDMS does not impose any constraint on
        how configuration files are formatted, although YAML is
        recommended. A template of a model's configuration file
        with placeholder values is used by the BMI.
        """
        # Convert cfg into a DictConfig obj. We need the cfg in a string format for BMI
        self.cfg = OmegaConf.create(eval(config_file))

        self._grid_type = {0: "scalar"}
        self.device = self.cfg.device

        self._model = LGAR(self.cfg)
        self.dates, self.precipitation, self.PET = read_forcing_data(self.cfg)
        self._values = {
            "precipitation_rate": None,
            "potential_evapotranspiration_rate": None,
            "soil_moisture_wetting_fronts": None,
            "soil_depth_wetting_fronts": None,
        }
        self._var_units = {
            "precipitation_rate": "(mm / h)",
            "potential_evapotranspiration_rate": "(mm / h)",
            "soil_moisture_wetting_fronts": None,
            "soil_depth_wetting_fronts": None,
        }

        self._end_time = self.cfg.data.endtime
        self.timestep = self.cfg.data.timestep
        self.nsteps = int(self._end_time/self.timestep)
        self.cfg.variables.nsteps = self.nsteps

        assert (self.nsteps <= int(self.x.shape[0]))
        log.debug("Variables are written to file: data_variables.csv")
        log.debug("Wetting fronts state is written to file: data_layers.csv")

    def update(self) -> None:
        """Advance model state by one time step.

        Perform all tasks that take place within one pass through the model's
        time loop. This typically includes incrementing all of the model's
        state variables. If the model's state variables don't change in time,
        then they can be computed by the :func:`initialize` method and this
        method can return with no action.
        """
        if self._model.sft_coupled:
            self._model.frozen_factor_hydraulic_conductivity()

    def update_until(self, time: float) -> None:
        """Advance model state until the given time.

        Parameters
        ----------
        time : float
            A model time later than the current model time.
        """
        for i in range(time):
            self.set_value("precipitation_rate", self.precipitation[time])
            self.set_value("potential_evapotranspiration_rate", self.PET[time])
            self.update()

    def finalize(self) -> None:
        """Perform tear-down tasks for the model.

        Perform all tasks that take place after exiting the model's time
        loop. This typically includes deallocating memory, closing files and
        printing reports.
        """
        self._end_time = time.perf_counter()

        log.info(
            f"\n---------------------- Simulation Summary  ------------------------ \n"
        )
        log.info(f"Time (sec)                 = {self._end_time -self._start_time:.6f} \n")
        log.info(f"-------------------------- Mass balance ------------------- \n")
        log.info(f"initial water in soil      = {volstart} cm\n")
        log.info(f"total precipitation input  = {volprecip}cm\n")
        log.info(f"total infiltration         = {volin} cm\n")
        log.info(f"final water in soil        = {volend} cm\n")
        log.info(f"water remaining on surface = {volon} cm\n")
        log.info(f"surface runoff             = {volrunoff} cm\n")
        log.info(f"total percolation          = {volrech} cm\n")
        log.info(f"total AET                  = {volAET} cm\n")
        log.info(f"total PET                  = {volPET} cm\n")
        log.info(f"global balance             = {global_error_cm} cm\n")

    def get_component_name(self) -> str:
        """Name of the component.

        Returns
        -------
        str
            The name of the component.
        """
        raise NotImplementedError

    def get_input_item_count(self) -> int:
        """Count of a model's input variables.

        Returns
        -------
        int
          The number of input variables.
        """
        raise NotImplementedError

    def get_output_item_count(self) -> int:
        """Count of a model's output variables.

        Returns
        -------
        int
          The number of output variables.
        """
        raise NotImplementedError

    def get_input_var_names(self) -> Tuple[str]:
        """List of a model's input variables.

        Input variable names must be CSDMS Standard Names, also known
        as *long variable names*.

        Returns
        -------
        list of str
            The input variables for the model.

        Notes
        -----
        Standard Names enable the CSDMS framework to determine whether
        an input variable in one model is equivalent to, or compatible
        with, an output variable in another model. This allows the
        framework to automatically connect components.

        Standard Names do not have to be used within the model.
        """
        raise NotImplementedError

    def get_output_var_names(self) -> Tuple[str]:
        """List of a model's output variables.

        Output variable names must be CSDMS Standard Names, also known
        as *long variable names*.

        Returns
        -------
        list of str
            The output variables for the model.
        """
        raise NotImplementedError

    def get_var_grid(self, name: str) -> int:
        """Get grid identifier for the given variable.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.

        Returns
        -------
        int
          The grid identifier.
        """
        raise NotImplementedError

    def get_var_type(self, name: str) -> str:
        """Get data type of the given variable.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.

        Returns
        -------
        str
            The Python variable type; e.g., ``str``, ``int``, ``float``.
        """
        raise NotImplementedError

    def get_var_units(self, name: str) -> str:
        """Get units of the given variable.

        Standard unit names, in lower case, should be used, such as
        ``meters`` or ``seconds``. Standard abbreviations, like ``m`` for
        meters, are also supported. For variables with compound units,
        each unit name is separated by a single space, with exponents
        other than 1 placed immediately after the name, as in ``m s-1``
        for velocity, ``W m-2`` for an energy flux, or ``km2`` for an
        area.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.

        Returns
        -------
        str
            The variable units.

        Notes
        -----
        CSDMS uses the `UDUNITS`_ standard from Unidata.

        .. _UDUNITS: http://www.unidata.ucar.edu/software/udunits
        """
        raise NotImplementedError

    def get_var_itemsize(self, name: str) -> int:
        """Get memory use for each array element in bytes.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.

        Returns
        -------
        int
            Item size in bytes.
        """
        raise NotImplementedError

    def get_var_nbytes(self, name: str) -> int:
        """Get size, in bytes, of the given variable.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.

        Returns
        -------
        int
            The size of the variable, counted in bytes.
        """
        raise NotImplementedError

    def get_var_location(self, name: str) -> str:
        """Get the grid element type that the a given variable is defined on.

        The grid topology can be composed of *nodes*, *edges*, and *faces*.

        *node*
            A point that has a coordinate pair or triplet: the most
            basic element of the topology.

        *edge*
            A line or curve bounded by two *nodes*.

        *face*
            A plane or surface enclosed by a set of edges. In a 2D
            horizontal application one may consider the word “polygon”,
            but in the hierarchy of elements the word “face” is most common.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.

        Returns
        -------
        str
            The grid location on which the variable is defined. Must be one of
            `"node"`, `"edge"`, or `"face"`.

        Notes
        -----
        CSDMS uses the `ugrid conventions`_ to define unstructured grids.

        .. _ugrid conventions: http://ugrid-conventions.github.io/ugrid-conventions
        """
        raise NotImplementedError

    def get_current_time(self) -> float:
        """Current time of the model.

        Returns
        -------
        float
            The current model time.
        """
        raise NotImplementedError

    def get_start_time(self) -> float:
        """Start time of the model.

        Model times should be of type float.

        Returns
        -------
        float
            The model start time.
        """
        raise NotImplementedError

    def get_end_time(self) -> float:
        """End time of the model.

        Returns
        -------
        float
            The maximum model time.
        """
        return self._end_time

    def get_time_units(self) -> str:
        """Time units of the model.

        Returns
        -------
        str
            The model time unit; e.g., `days` or `s`.

        Notes
        -----
        CSDMS uses the UDUNITS standard from Unidata.
        """
        raise NotImplementedError

    def get_time_step(self) -> float:
        """Current time step of the model.

        The model time step should be of type float.

        Returns
        -------
        float
            The time step used in model.
        """
        raise NotImplementedError

    def get_value(self, name: str, dest: torch.Tensor) -> torch.Tensor:
        """Get a copy of values of the given variable.

        This is a getter for the model, used to access the model's
        current state. It returns a *copy* of a model variable, with
        the return type, size and rank dependent on the variable.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.
        dest : ndarray
            A numpy array into which to place the values.

        Returns
        -------
        ndarray
            The same numpy array that was passed as an input buffer.
        """
        raise NotImplementedError

    def get_value_ptr(self, name: str) -> torch.Tensor:
        """Get a reference to values of the given variable.

        This is a getter for the model, used to access the model's
        current state. It returns a reference to a model variable,
        with the return type, size and rank dependent on the variable.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.

        Returns
        -------
        array_like
            A reference to a model variable.
        """
        return self._values[name]

    def get_value_at_indices(
        self, name: str, dest: torch.Tensor, inds: torch.Tensor
    ) -> torch.Tensor:
        """Get values at particular indices.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.
        dest : ndarray
            A numpy array into which to place the values.
        inds : array_like
            The indices into the variable array.

        Returns
        -------
        array_like
            Value of the model variable at the given location.
        """
        raise NotImplementedError

    def set_value(self, name: str, src: torch.Tensor) -> None:
        """Specify a new value for a model variable.

        This is the setter for the model, used to change the model's
        current state. It accepts, through *src*, a new value for a
        model variable, with the type, size and rank of *src*
        dependent on the variable.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.
        src : array_like
            The new value for the specified variable.
        """


    def set_value_at_indices(
        self, name: str, inds: torch.Tensor, src: torch.Tensor
    ) -> None:
        """Specify a new value for a model variable at particular indices.

        Parameters
        ----------
        name : str
            An input or output variable name, a CSDMS Standard Name.
        inds : array_like
            The indices into the variable array.
        src : array_like
            The new value for the specified variable.
        """
        raise NotImplementedError

    # Grid information
    def get_grid_rank(self, grid: int) -> int:
        """Get number of dimensions of the computational grid.

        Parameters
        ----------
        grid : int
            A grid identifier.

        Returns
        -------
        int
            Rank of the grid.
        """
        raise NotImplementedError

    def get_grid_size(self, grid: int) -> int:
        """Get the total number of elements in the computational grid.

        Parameters
        ----------
        grid : int
            A grid identifier.

        Returns
        -------
        int
            Size of the grid.
        """
        raise NotImplementedError

    def get_grid_type(self, grid: int) -> str:
        """Get the grid type as a string.

        Parameters
        ----------
        grid : int
            A grid identifier.

        Returns
        -------
        str
            Type of grid as a string.
        """
        raise NotImplementedError

    # Uniform rectilinear
    def get_grid_shape(self, grid: int, shape: torch.Tensor) -> torch.Tensor:
        """Get dimensions of the computational grid.

        Parameters
        ----------
        grid : int
            A grid identifier.
        shape : ndarray of int, shape *(ndim,)*
            A numpy array into which to place the shape of the grid.

        Returns
        -------
        ndarray of int
            The input numpy array that holds the grid's shape.
        """
        raise NotImplementedError

    def get_grid_spacing(self, grid: int, spacing: torch.Tensor) -> torch.Tensor:
        """Get distance between nodes of the computational grid.

        Parameters
        ----------
        grid : int
            A grid identifier.
        spacing : ndarray of float, shape *(ndim,)*
            A numpy array to hold the spacing between grid rows and columns.

        Returns
        -------
        ndarray of float
            The input numpy array that holds the grid's spacing.
        """
        raise NotImplementedError

    def get_grid_origin(self, grid: int, origin: torch.Tensor) -> torch.Tensor:
        """Get coordinates for the lower-left corner of the computational grid.

        Parameters
        ----------
        grid : int
            A grid identifier.
        origin : ndarray of float, shape *(ndim,)*
            A numpy array to hold the coordinates of the lower-left corner of
            the grid.

        Returns
        -------
        ndarray of float
            The input numpy array that holds the coordinates of the grid's
            lower-left corner.
        """
        raise NotImplementedError

    # Non-uniform rectilinear, curvilinear
    def get_grid_x(self, grid: int, x: torch.Tensor) -> torch.Tensor:
        """Get coordinates of grid nodes in the x direction.

        Parameters
        ----------
        grid : int
            A grid identifier.
        x : ndarray of float, shape *(nrows,)*
            A numpy array to hold the x-coordinates of the grid node columns.

        Returns
        -------
        ndarray of float
            The input numpy array that holds the grid's column x-coordinates.
        """
        raise NotImplementedError

    def get_grid_y(self, grid: int, y: torch.Tensor) -> torch.Tensor:
        """Get coordinates of grid nodes in the y direction.

        Parameters
        ----------
        grid : int
            A grid identifier.
        y : ndarray of float, shape *(ncols,)*
            A numpy array to hold the y-coordinates of the grid node rows.

        Returns
        -------
        ndarray of float
            The input numpy array that holds the grid's row y-coordinates.
        """
        raise NotImplementedError

    def get_grid_z(self, grid: int, z: torch.Tensor) -> torch.Tensor:
        """Get coordinates of grid nodes in the z direction.

        Parameters
        ----------
        grid : int
            A grid identifier.
        z : ndarray of float, shape *(nlayers,)*
            A numpy array to hold the z-coordinates of the grid nodes layers.

        Returns
        -------
        ndarray of float
            The input numpy array that holds the grid's layer z-coordinates.
        """
        raise NotImplementedError

    def get_grid_node_count(self, grid: int) -> int:
        """Get the number of nodes in the grid.

        Parameters
        ----------
        grid : int
            A grid identifier.

        Returns
        -------
        int
            The total number of grid nodes.
        """
        raise NotImplementedError

    def get_grid_edge_count(self, grid: int) -> int:
        """Get the number of edges in the grid.

        Parameters
        ----------
        grid : int
            A grid identifier.

        Returns
        -------
        int
            The total number of grid edges.
        """
        raise NotImplementedError

    def get_grid_face_count(self, grid: int) -> int:
        """Get the number of faces in the grid.

        Parameters
        ----------
        grid : int
            A grid identifier.

        Returns
        -------
        int
            The total number of grid faces.
        """
        raise NotImplementedError

    def get_grid_edge_nodes(self, grid: int, edge_nodes: torch.Tensor) -> torch.Tensor:
        """Get the edge-node connectivity.

        Parameters
        ----------
        grid : int
            A grid identifier.
        edge_nodes : ndarray of int, shape *(2 x nnodes,)*
            A numpy array to place the edge-node connectivity. For each edge,
            connectivity is given as node at edge tail, followed by node at
            edge head.

        Returns
        -------
        ndarray of int
            The input numpy array that holds the edge-node connectivity.
        """
        raise NotImplementedError

    def get_grid_face_edges(self, grid: int, face_edges: torch.Tensor) -> torch.Tensor:
        """Get the face-edge connectivity.

        Parameters
        ----------
        grid : int
            A grid identifier.
        face_edges : ndarray of int
            A numpy array to place the face-edge connectivity.

        Returns
        -------
        ndarray of int
            The input numpy array that holds the face-edge connectivity.
        """
        raise NotImplementedError

    def get_grid_face_nodes(self, grid: int, face_nodes: torch.Tensor) -> torch.Tensor:
        """Get the face-node connectivity.

        Parameters
        ----------
        grid : int
            A grid identifier.
        face_nodes : ndarray of int
            A numpy array to place the face-node connectivity. For each face,
            the nodes (listed in a counter-clockwise direction) that form the
            boundary of the face.

        Returns
        -------
        ndarray of int
            The input numpy array that holds the face-node connectivity.
        """
        raise NotImplementedError

    def get_grid_nodes_per_face(
        self, grid: int, nodes_per_face: torch.Tensor
    ) -> torch.Tensor:
        """Get the number of nodes for each face.

        Parameters
        ----------
        grid : int
            A grid identifier.
        nodes_per_face : ndarray of int, shape *(nfaces,)*
            A numpy array to place the number of nodes per face.

        Returns
        -------
        ndarray of int
            The input numpy array that holds the number of nodes per face.
        """
        raise NotImplementedError
