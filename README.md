[![Tests](https://github.com/systemiqofficial/mpp-shared-code/actions/workflows/testing.yml/badge.svg)](https://github.com/systemiqofficial/mpp-shared-code/actions/workflows/testing.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)


# MPP Shared Code

This is a repository with the shared utility and logic code for a MPP STS Models. It also scontains a Python script to install the library, CI/CD workflow with automated testing.


### How to use it

Once the changes are made, the repository is ready to start coding on. The repository comes with two branches `main` and `develop` to follow the gitflow workflow. These branches are protected by default, so it cannot be pushed directly to them, and all the changes need to be made via a Pull Request.

The library code should be written in corresponding folders and it is accessible by importing the library by the name (e.g.. `import mppshared`). It is possible to use the library in other scripts while developing it, any script written in the root directory can access the library without need to be installed, otherwise it is possible to install the library and make it accessible for all the computer with the following command.

```bash
python setup.py develop
```

Make sure to write the tests in the `tests/` directory, name the test files with `test_{MODULE_NAME}`, the tests can be run with the testing scripts, make sure to read the README](tests/README.md) in the tests directory.

#### Conda development environment

The repository includes a pre-defined conda development environment, it can be installed navigating to the tests directory and with the following command:

```bash
conda env create -f environment-dev.yml
```

#### Code style

The repository uses black as a code formatter. From README:

Black is the uncompromising Python code formatter. By using it, you agree to cede control over minutiae of hand-formatting. In return, Black gives you speed, determinism, and freedom from pycodestyle nagging about formatting. You will save time and mental energy for more important matters.

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
- [Shajeeshan Lingeswaran](shajeeshan.lingeswaran@systemiq.earth)
