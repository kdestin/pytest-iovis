from pathlib import Path
from typing import Optional

import pytest

from ._subplugins import NotebookMarkerArg, NotebookMarkerHandler


@pytest.fixture(name=NotebookMarkerHandler.FIXTURE_NAME)
def notebook_path(request: pytest.FixtureRequest) -> Path:
    """Return the path to the notebook under test."""
    param: Optional[object] = getattr(request, "param", None)
    if not isinstance(param, NotebookMarkerArg):
        pytest.fail(
            f"Fixture {notebook_path.__name__!r} requested from function without @pytest.mark.notebook marker.",
            pytrace=False,
        )

    return param.resolved_path
