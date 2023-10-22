from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union, cast

import papermill as pm  # type: ignore[import-untyped]
import pytest
from nbformat import NotebookNode

from .discovery import JupyterNotebookDiscoverer, register_default_test_functions
from .notebook_marker import NotebookMarkerHandler


def test_notebook_runs(
    notebook_path: Path,
    notebook_output_path: Path,
    notebook_parameters: Dict[str, Any],
    notebook_extra_arguments: Iterable[str],
) -> None:
    cast(
        NotebookNode,
        pm.execute_notebook(
            notebook_path,
            notebook_output_path,
            parameters=notebook_parameters,
            extra_arguments=list(notebook_extra_arguments),
        ),
    )


class PapermillTestRunner:
    """Provides a test function and fixtures to faciliate running notebooks with papermill."""

    PLUGIN_NAME = "papermill_runner"
    """A user facing name that describes this plugin."""

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
