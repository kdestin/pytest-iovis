import functools
import os
from pathlib import Path
from typing import Callable, Optional, Union

import nbformat
import pytest

pytest_plugins = ["pytester"]


@pytest.fixture()
def dummy_notebook_factory(testdir: pytest.Testdir) -> Callable[[Optional[Union["os.PathLike[str]", str]]], Path]:
    """Return a Callable that can be used to generate empty (dummy) notebooks.

    The callable accepts either:
        * A path that the notebook is written to
        * A falsy value, which signals that any path may be used
    """
    nb: nbformat.NotebookNode = nbformat.v4.new_notebook()  # type: ignore[no-untyped-call]
    nb["metadata"]["kernelspec"] = {"name": "python3", "language": "python", "display_name": "Python 3"}
    notebook_string: str = nbformat.writes(nb)  # type: ignore[no-untyped-call]

    @functools.wraps(dummy_notebook_factory)  # type: ignore[misc]
    def toReturn(filename: Optional[Union["os.PathLike[str]", str]] = None) -> Path:
        if filename:
            return Path(testdir.makefile(".ipynb", **{str(Path(filename).with_suffix("")): notebook_string}))
        return Path(testdir.makefile(".ipynb", notebook_string))

    return toReturn


@pytest.fixture()
def dummy_notebook(dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path]) -> Path:
    """Return a Jupyter notebook that always runs successfully."""
    return dummy_notebook_factory(None)
