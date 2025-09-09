#!/bin/bash

echo "Running Playwright Auth POC tests..."

# Activate virtual environment and run tests
source .venv/bin/activate
pytest tests/ -v
