[![Tests](https://github.com/systemiqofficial/mpp-shared-code/actions/workflows/testing.yml/badge.svg)](https://github.com/systemiqofficial/mpp-shared-code/actions/workflows/testing.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)


# MPP Shared Industry Solver

This repository contains the MPP Shared Industry Solver and the Ammonia and Aluminium models. Both models were developed as part of the [Mission Possible Partnership](https://www.missionpossiblepartnership.org) (MPP). The MPP Shared Industry Solver is a Python package that can be used to build industry decarbonization models. The Ammonia and Aluminium models are examples of how to use the building blocks provided in the MPP Solver.

## How to use it

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
- `mppshared.solver`:

#### Code style

The repository uses black as a code formatter. From README:

>Black is the uncompromising Python code formatter. By using it, you agree to cede control over minutiae of hand-formatting. In return, Black gives you speed, determinism, and freedom from pycodestyle nagging about formatting. You will save time and mental energy for more important matters.

Blackened code looks the same regardless of the project you're reading. Formatting becomes transparent after a while and you can focus on the content instead.

Black makes code review faster by producing the smallest diffs possible.

You can configure your editor to use Black by default and format the code every time it is saved.

+ [VSCode](https://code.visualstudio.com/docs/python/editing#_formatting)
+ [PyCharm](https://black.readthedocs.io/en/stable/integrations/editors.html#pycharm-intellij-idea)

For sorting the imports and the repository uses `isort`, it sort imports alphabetically, and automatically separated into sections and by type. As with Black, isort can be used directly in the [code editors](https://github.com/pycqa/isort/wiki/isort-Plugins).

Both black and isort are installed by default in the `mpp-dev` conda environment. To automatically format the code, move to the repository's root directory and run the following:

```bash
bash ./tests/black.sh
```

## Project Context

## Project Goals

## Installation

To install it with pip directly from GitHub:

```bash
pip install git+https://${YOUR_GITHUB_TOKEN}@github.com/systemiqofficial/mpp-shared-code.git
```

Change the `YOUR_GITHUB_TOKEN` to your personal access token. You can create one in https://github.com/settings/tokens.

### Installation from source

To install MPP-SHARED-CODE from source you will need the dependencies, and in the mppshared folder execute:

```bash
python setup.py install
```

## Useful resources

+ [Official MPP Website](https://missionpossiblepartnership.org/)
+ [Energy Transistions Commission](https://www.energy-transitions.org/)

## Setting up and running the model
Set up a conda environnment using the environment.yml file

To create a new environment:

```bash
conda env create -f environment.yml
```

## Contributing

All contributions, bug reports, bug fixes, documentation improvements, code enhancements, and ideas are welcome.

Before opening a pull request make sure to check the code format, linting and Continuous Integration process [here.](tests/README.md)

### Development environment

There is a development environment, to install it:

```bash
conda env create -f tests/environment-dev.yml
```

## Contacts

### Technical questions

- [Andrew Isabirye](andrew.isabirye@systemiq.earth)
- [Luis Natera](luis.natera@systemiq.earth)
- [Pim Sauter](pim.sauter@systemiq.earth)
