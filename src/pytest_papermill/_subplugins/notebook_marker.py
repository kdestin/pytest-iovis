import os
from pathlib import Path
from typing import Union

import pytest

from .._utils import make_mark_description


def notebook(path: Union[os.PathLike, str]) -> Path:
    """Associate a test function with a Jupyter Notebook.

    This function is only used to generate documentation for the `notebook` marker (docstring + signature)
    """
    return path


class NotebookMarkerHandler:
    """A pytest plugin that manages the semantics of the `@pytest.mark.notebook` mark."""

    MARKER_NAME = notebook.__name__
    """The name of the marker managed by this plugin"""

    def pytest_configure(self, config: pytest.Config) -> None:
        """Register the marker handled by this plugin"""

        config.addinivalue_line("markers", make_mark_description(notebook))
