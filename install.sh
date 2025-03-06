#! /bin/bash

PACKAGE_NAME="aws-scripts"

# Check&Install poetry
if ! command -v poetry &> /dev/null
then
  echo "Install poetry"
  pip3 install poetry
fi

# Check&Install pipx
if ! command -v pipx &> /dev/null
then
  echo "Install pipx"
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
fi


# Create venv and build package
poetry install
poetry build

VENV_NAME=$(poetry env list)
#poetry env remove "${VENV_NAME//\(Activated)/}"
WHL_PACKAGE_NAME=$(ls dist/*.whl)
# Uninstall for update without change version number
pipx uninstall ${PACKAGE_NAME}
pipx install --force "${WHL_PACKAGE_NAME}"

rm -drf dist