from pathlib import Path
from typing import Optional

import pytest

from . import _fixtures
from ._file import JupyterNotebookFile
from ._subplugins import IPythonMarkupPlugin


def pytest_configure(config: pytest.Config):
    config.pluginmanager.register(_fixtures)
    config.pluginmanager.register(IPythonMarkupPlugin())


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> Optional[pytest.Collector]:
    if file_path.suffix in [".ipynb"]:
        return JupyterNotebookFile.from_parent(parent, path=file_path)
    return None
