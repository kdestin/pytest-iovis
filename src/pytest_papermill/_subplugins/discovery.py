from pathlib import Path
from typing import Optional

import pytest

from .._file import JupyterNotebookFile


class JupyterNotebookDiscoverer:
    """A pytest plugin that enables auto-discovery of Jupyter notebooks as pytest tests"""

    def pytest_collect_file(self, file_path: Path, parent: pytest.Collector) -> Optional[pytest.Collector]:
        if file_path.suffix in [".ipynb"]:
            return JupyterNotebookFile.from_parent(parent, path=file_path)
        return None
