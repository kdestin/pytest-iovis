import functools
import json
from pathlib import Path
from typing import Callable, Optional

import pytest

from pytest_iovis import PathType

pytest_plugins = ["pytester"]


@pytest.fixture()
def dummy_notebook_factory(testdir: pytest.Testdir) -> Callable[[Optional[PathType]], Path]:
    """Return a Callable that can be used to generate empty (dummy) notebooks.

    The callable accepts either:
        * A path that the notebook is written to
        * A falsy value, which signals that any path may be used
    """
    notebook_string: str = json.dumps(
        {
            "cells": [],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    )

    @functools.wraps(dummy_notebook_factory)  # type: ignore[misc]
    def toReturn(filename: Optional[PathType] = None) -> Path:
        if filename:
            return Path(testdir.makefile(".ipynb", **{str(Path(filename).with_suffix("")): notebook_string}))
        return Path(testdir.makefile(".ipynb", notebook_string))

    return toReturn


@pytest.fixture()
def dummy_notebook(dummy_notebook_factory: Callable[[Optional[PathType]], Path]) -> Path:
    """Return a Jupyter notebook that always runs successfully."""
    return dummy_notebook_factory(None)
