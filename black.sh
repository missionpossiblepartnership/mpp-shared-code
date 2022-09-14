#!/bin/bash
isort --profile black .
black . --line-length 88
