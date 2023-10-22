from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union, cast

import papermill as pm  # type: ignore[import-untyped]
import pytest
from nbformat import NotebookNode

from .discovery import JupyterNotebookDiscoverer, register_default_test_functions
from .markup import IPythonMarkupPlugin
from .notebook_marker import NotebookMarkerHandler


def test_notebook_runs(
    notebook_path: Path,
    papermill_output_path: Path,
    papermill_parameters: Dict[str, Any],
    papermill_extra_arguments: Iterable[str],
) -> None:
    cast(
        NotebookNode,
        pm.execute_notebook(
            notebook_path,
            papermill_output_path,
            parameters=papermill_parameters,
            extra_arguments=list(papermill_extra_arguments),
        ),
    )


class PapermillTestRunner:
    """Provides a test function and fixtures to faciliate running notebooks with papermill."""

    PLUGIN_NAME = "papermill_runner"
    """A user facing name that describes this plugin."""

    @pytest.fixture()
    def papermill_parameters(self) -> Dict[str, Any]:
        """Return a dictionary used to parameterize a Jupyter Notebook with Papermill.

        Keys must be suitable to be used as a python identitifer. Values must be a JSON encodable value

        .. see-also::

            https://papermill.readthedocs.io/en/latest/usage-parameterize.html
        """
        return {}

    @pytest.fixture()
    def papermill_output_path(self, notebook_path: Path, tmp_path: Path) -> Optional[Path]:
        """Return the path to write the notebook output to.

        Defaults to `tmp_path / notebook_path.with_suffix(".output.ipynb").name`.

        Can return `None` to disable notebook output.
        """
        return tmp_path / notebook_path.with_suffix(".output.ipynb").name

    @pytest.fixture(scope="session")
    def papermill_extra_arguments(self, request: pytest.FixtureRequest) -> Iterable[str]:
        """Return a iterable suitable to be provided as the extra_arguments parameter for papermill.execute_notebook."""
        style_plugin: Optional[IPythonMarkupPlugin] = next(
            (p for p in request.config.pluginmanager.get_plugins() if isinstance(p, IPythonMarkupPlugin)), None
        )

        if style_plugin:
            return (style_plugin.get_ipython_markup_arg(),)

        return ()

    @pytest.hookimpl(trylast=True)
    def pytest_configure(self, config: pytest.Config) -> None:
        if JupyterNotebookDiscoverer.test_functions(config) is None:
            register_default_test_functions(test_notebook_runs, config=config)

    def pytest_exception_interact(
        self,
        node: Union[pytest.Item, pytest.Collector],
        call: pytest.CallInfo[object],
        report: Union[pytest.CollectReport, pytest.TestReport],
    ) -> None:
        """Reformat the failure represention if the exception is a papermill.PapermillExecutationError."""
        if not (isinstance(report, pytest.TestReport) and NotebookMarkerHandler.is_marked_function(node)):
            return

        if call.when != "call":
            return

        excinfo: Optional[pytest.ExceptionInfo[BaseException]] = call.excinfo
        if excinfo is None or not isinstance(excinfo.value, pm.PapermillExecutionError):
            return

        report.longrepr = "\n".join(excinfo.value.traceback)
