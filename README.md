# Poetry Project

[![Poetry](https://img.shields.io/badge/poetry-1.x-blue.svg)](https://python-poetry.org/)
[![Python Versions](https://img.shields.io/pypi/pyversions/my_project_name.svg)](https://pypi.org/project/my_project_name/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
This project is managed using [Poetry](https://python-poetry.org/), a tool for dependency management and packaging in Python.

## Prerequisites

Make sure you have Poetry installed on your system. If not, you can install it by following the instructions on the [official Poetry website](https://python-poetry.org/docs/#installation).

## Getting Started
1.  **Install project dependencies:**

    Poetry uses the `pyproject.toml` file to manage dependencies. To install all the required packages, run the following command in the project root directory:

    ```bash
    poetry install
    ```

    This command will:
    * Read the `pyproject.toml` file.
    * Resolve the dependencies.
    * Create a `poetry.lock` file, which ensures consistent dependency versions across different environments.
    * Install the dependencies in a virtual environment managed by Poetry.

## Running the Project

To execute the main script or any other entry points defined in your `pyproject.toml`, you can use `poetry run`:

```bash

usage: poetry run gargantua [-h] [--gui] [--source SOURCE] --destination DESTINATION [--project PROJECT] --input_date INPUT_DATE [--data_type DATA_TYPE] [--mov] [--process {0,1}] [--vendor VENDOR] [--hires] [--camera CAMERA] [--take TAKE][--resolution RESOLUTION] [--force] [--proxy FORMAT]

poetry run gargantua --source <project root path> --destination <out> --input_date <YYYYmmdd>
