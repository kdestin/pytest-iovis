from pathlib import Path

import nbformat
import pytest

pytest_plugins = ["pytester"]


@pytest.fixture()
def dummy_notebook(testdir: pytest.Testdir) -> Path:
    """A jupyter notebook that always runs successfully."""
    nb = nbformat.v4.new_notebook()
    nb["metadata"]["kernelspec"] = {"name": "python3", "language": "python", "display_name": "Python 3"}
    return Path(testdir.makefile(".ipynb", nbformat.writes(nb)))
