
#!/bin/bash

# exit on error
set -e

# delete temp files and folders
rm -r -f .coverage .pytest_cache .temp ./docs/build cityBrain/__pycache__ tests/__pycache__ scripts/__pycache__
find . -type f -name "*.vrt" -delete

# check if imports are organized properly
isort --profile black . --check-only

# check if code is formatted properly
black . --line-length 88 --check --diff

# lint the code
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

# lint the docstrings
# pydocstyle .

# build the docs
# make -C ./docs html

# run the tests
coverage run --source ./mppshared --module pytest --verbose

# report the test coverage
coverage report -m

# delete temp files and folders
rm -r -f .coverage .pytest_cache .temp ./docs/build cityBrain/__pycache__ tests/__pycache__
find . -type f -name "*.vrt" -delete
