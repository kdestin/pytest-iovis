from pathlib import Path
from typing import Any, Dict

import pytest


@pytest.fixture()
def notebook_parameters() -> Dict[str, Any]:
    return {}


@pytest.fixture()
def notebook_path(request: pytest.FixtureRequest) -> Path:
    return request.path


@pytest.fixture()
def notebook_output_path(notebook_path: Path) -> Path:
    """Path to output jupyter notebook with output"""
    return notebook_path.parent / f"{notebook_path.stem}.output.ipynb"
