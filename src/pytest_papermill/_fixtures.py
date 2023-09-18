from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pytest

from ._subplugins import IPythonMarkupPlugin


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


@pytest.fixture(scope="session")
def notebook_extra_arguments(request: pytest.FixtureRequest) -> Iterable[str]:
    """Return a iterable suitable to be provided as the extra_arguments parameter for papermill.execute_notebook"""
    style_plugin: Optional[IPythonMarkupPlugin] = next(
        (p for p in request.config.pluginmanager.get_plugins() if isinstance(p, IPythonMarkupPlugin)), None
    )

    if style_plugin:
        return (style_plugin.get_ipython_markup_arg(),)

    return ()
