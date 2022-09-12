[![Tests](https://github.com/systemiqofficial/mpp-shared-code/actions/workflows/testing.yml/badge.svg)](https://github.com/systemiqofficial/mpp-shared-code/actions/workflows/testing.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)


# MPP Shared Industry Solver

This repository contains the MPP Shared Industry Solver and the Ammonia and Aluminium models. Both models were developed as part of the [Mission Possible Partnership](https://www.missionpossiblepartnership.org) (MPP). The MPP Shared Industry Solver is a Python package that can be used to build industry decarbonization models. The Ammonia and Aluminium models are examples of how to use the building blocks provided in the MPP Solver.

## How to use it

To start using the code, you can clone the repository and install the required packages using the following commands:

```bash
git clone
cd mpp-shared-code
pip install -r requirements.txt
```

The main files for the MPP shared solver are in the `mppshared` package. The `mppshared` package contains the following modules:

- `mppshared.import_data.intermediate_data`: Stores the `IntermediateDataImporter` class, which provides methods to retrieve all the different datafiles needed for the simulations.
- `mppshared.models`: Contains the different Classes used to build the models.
  - `mppshared.models.asset`: Contains the `Asset` class, this class is used to store the assets through the simulation, and it contains multiple parameters and methods to work with. Besides the `Asset` class it also includes an `AssetStack` class to store all the assets that are available during a given year in a simulation.
  - `mppshared.models.simulation_pathway`: Contains the `SimulationPathway` class, this class is used to store the simulation pathways, and it contains all the parameters needed to describe the pathway running, and methods to interact with the pathway (e.g. calculate the emissions for a given year, get the stack for a given year, etc).
  - `mppshared.models.transition`: Contains the `TransitionRegistry` class, used to track the different transitions that have been applied to the assets in the simulation. This class can produce a `pandas.DataFrame` with all the transitions.
  - `mppshared.models.carbon_budget`: Contains the `CarbonBudget` class, used to store the carbon budget for a sector, it can produce different carbon budget shapes by taking the start, end year. IT also has a method to access the emission limit for a given year.
  - `mppshared.models.carbon_cost_trajectory`: Contains a `CarbonCost` class to define the trajectory of the carbon cost to be applied to the different transitions based on the technology destination emissions.
  - `mppshared.models.constraints`: A collection of different constraints to be used with the model, THe constraints are applied each time the model wants to make a transition, each constraint returns a boolean value indicating if the transition is allowed or not.
- `mppshared.agent_logic`: Contains the different actions that can be implemented in a company asset:
  - `mppshared.agent_logic.brownfield`: It has the actions to enact a retrofit in a brownfield asset.
  - `mppshared.agent_logic.greenfield`: It has the actions to build a new greenfield asset.
  - `mppshared.agent_logic.decommission`: It has the actions to decommission an asset.
  - `mppshared.agent_logic.agent_logic_functions`: Shared functions for the previously described modules.
- `mppshared.solver`: This modul contains different submodules used to solve the simulations, the most relevant are:
  - `mppshared.solver.implicit_forcing`: Contains the different functions used to simulate the implicit forcing mechanisms in the available transitions, such as filtering out non logical transitions (end-state to initial technologies), add carbon costs to the ranking metric, apply technology moratoriums, etc.
  - `mppshared.solver.ranking` Contains the functions used to create the ranking tables to be used while deciding to which technology transition. Currently, the ranking can be calculated as an histogram, or by uncertainty bins.

Using this modules it is possible to build simulations like the ones for Aluminium and Ammonia. Both of these sector use the building block provided in the `mppshared` library to build their models.

### How to run the simulations

The Aluminium and Ammonia code are stored in their own folders, it is possible to run either of them directly from `main.py`, the only configuration needed is to change the name of the sector in the `main.py` file. The code will run the simulation for the sector and save the results in the `{sector}/data/{pathway}/final` folder.

Each sector has a `config_{sector}.py` file to store the different configurations available to the model, such as `START_YEAR`, END_YEAR` for the simulations, pathways to run, constraints to apply, and ranking configurations.

Each sector has their own `main_{sector}.py` file that controls the different steps of the simulation and calls the different functions to load the data, apply the implicit forcing mechanisms, make the ranking tables, run the simulation, and produce the results.

The `solver` inside each of the sectors, contains the dedicated files to run the simulation, these files are built using the classes and methods from `mppshared`.

## Contributing

All contributions, bug reports, bug fixes, documentation improvements, code enhancements, and ideas are welcome.

To contribute to the code you can fork the repository and create a pull request with your changes. The code is formatted using `black` and `isort`, so it is recommended to use these tools to format the code before creating the pull request. Make sure that the tests pass before creating the pull request.

## Useful resources

+ [Official MPP Website](https://missionpossiblepartnership.org/)
+ [Energy Transition Commission](https://www.energy-transitions.org/)

## Contacts

For any questions, please contact [MPP](mailto:).

### Contributors

- [Andrew Isabirye](andrew.isabirye@systemiq.earth)
- [Luis Natera](luis.natera@systemiq.earth)
- [Johannes Wullenweber]()
- [Timon Ruckel]()
