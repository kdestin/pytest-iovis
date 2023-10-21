from pathlib import Path
from typing import Any, Dict, Iterable, Optional, cast

import pytest

from ._subplugins import IPythonMarkupPlugin, NotebookMarkerArg, NotebookMarkerHandler


@pytest.fixture()
def notebook_parameters() -> Dict[str, Any]:
    """Return a dictionary used to parameterize a Jupyter Notebook with Papermill.

    Keys must be suitable to be used as a python identitifer. Values must be a JSON encodable value

    .. see-also::

        https://papermill.readthedocs.io/en/latest/usage-parameterize.html
    """
    return {}


@pytest.fixture(name=NotebookMarkerHandler.FIXTURE_NAME)
def notebook_path(request: pytest.FixtureRequest) -> Path:
    """Return the path to the notebook under test."""
    param: Optional[object] = getattr(request, "param", None)
    if not isinstance(param, NotebookMarkerArg):
        pytest.fail(
            f"Fixture {notebook_path.__name__!r} requested from function without @pytest.mark.notebook marker.",
            pytrace=False,
        )

    return cast(NotebookMarkerArg, param).resolved_path


@pytest.fixture()
def notebook_output_path(notebook_path: Path, tmp_path: Path) -> Optional[Path]:
    """Return the path to write the notebook output to.

    Defaults to `tmp_path / notebook_path.with_suffix(".output.ipynb").name`.

    Can return `None` to disable notebook output.
    """
    return tmp_path / notebook_path.with_suffix(".output.ipynb").name


@pytest.fixture(scope="session")
def notebook_extra_arguments(request: pytest.FixtureRequest) -> Iterable[str]:
    """Return a iterable suitable to be provided as the extra_arguments parameter for papermill.execute_notebook."""
    style_plugin: Optional[IPythonMarkupPlugin] = next(
        (p for p in request.config.pluginmanager.get_plugins() if isinstance(p, IPythonMarkupPlugin)), None
    )

    if style_plugin:
        return (style_plugin.get_ipython_markup_arg(),)

    return ()
