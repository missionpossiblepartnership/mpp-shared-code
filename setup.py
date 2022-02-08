"""
mppaluminium setup script.
For licence information, see licence.txt
"""
import os

from setuptools import setup

# only specify install_requires if not in RTD environment
if os.getenv("READTHEDOCS") == "True":
    INSTALL_REQUIRES = []
else:
    with open("requirements.txt") as f:
        INSTALL_REQUIRES = [line.strip() for line in f.readlines()]

# Basic setup information of the library
setup(
    name="{LIBRARY-NAME}",
    version="0.1",
    description="{LIBRARY-DESCRIPTION}",
    author="SYSTEMIQ",
    packages=["{LIBRARY-NAME}"],
    python_requires=">=3.9",
    install_requires=INSTALL_REQUIRES,
)
