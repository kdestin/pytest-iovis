import functools
import os
from pathlib import Path
from typing import Callable, Optional, Union

import nbformat
import pytest

pytest_plugins = ["pytester"]


@pytest.fixture()
def dummy_notebook_factory(testdir: pytest.Testdir) -> Callable[[Optional[Union[os.PathLike, str]]], Path]:
    """A callable that returns a jupyter notebook that runs successfully at the specified path. A falsy argument
    generates a test specific path."""
    nb = nbformat.v4.new_notebook()
    nb["metadata"]["kernelspec"] = {"name": "python3", "language": "python", "display_name": "Python 3"}
    notebook_string = nbformat.writes(nb)

    @functools.wraps(dummy_notebook_factory)
    def toReturn(filename: Optional[str] = None) -> Path:
        if filename:
            return Path(testdir.makefile(".ipynb", **{str(Path(filename).with_suffix("")): notebook_string}))
        return Path(testdir.makefile(".ipynb", notebook_string))

    return toReturn


@pytest.fixture()
def dummy_notebook(dummy_notebook_factory: Callable[[Optional[Union[os.PathLike, str]]], Path]) -> Path:
    """A jupyter notebook that always runs successfully."""
    return dummy_notebook_factory(None)
