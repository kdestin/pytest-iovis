from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union, cast

import papermill as pm  # type: ignore[import-untyped]
import pytest
from nbformat import NotebookNode

from .._types import TestObject
from .discovery import JupyterNotebookDiscoverer
from .markup import IPythonMarkupPlugin


def test_notebook_runs(papermill_execute: Callable[[], NotebookNode]) -> None:
    """Validates that notebook runs without raising exceptions."""
    papermill_execute()


class PapermillTestRunner:
    """Provides a test function and fixtures to facilitate running notebooks with papermill."""

    PLUGIN_NAME = "papermill_runner"
    """A user facing name that describes this plugin."""

    @pytest.fixture()
    def papermill_execute(
        self,
        notebook_path: Path,
        papermill_output_path: Optional[Path],
        papermill_parameters: Dict[str, Any],
        papermill_extra_arguments: List[str],
        papermill_cwd: Optional[Path],
    ) -> Callable[[], NotebookNode]:
        """Return a Callable[[], NotebookNode] that runs a notebook. Configurable with papermill_* fixtures."""
        return lambda: cast(
            NotebookNode,
            pm.execute_notebook(
                notebook_path,
                papermill_output_path,
                parameters=papermill_parameters,
                extra_arguments=papermill_extra_arguments,
                cwd=papermill_cwd,
            ),
        )

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

    @pytest.fixture()
    def papermill_extra_arguments(self, request: pytest.FixtureRequest) -> List[str]:
        """Return a list passed as the extra_arguments parameter for papermill.execute_notebook."""
        style_plugin: Optional[IPythonMarkupPlugin] = next(
            (p for p in request.config.pluginmanager.get_plugins() if isinstance(p, IPythonMarkupPlugin)), None
        )

        if style_plugin:
            return [style_plugin.get_ipython_markup_arg()]

        return []

    @pytest.fixture()
    def papermill_cwd(self, notebook_path: Path) -> Optional[Path]:
        """Return the path to execute notebooks from. Defaults to notebook's directory.

        If set to None, will run in the current working directory.
        """
        return notebook_path.parent

    def pytest_iovis_set_tests(self) -> Iterable[TestObject]:
        yield test_notebook_runs

    def pytest_exception_interact(
        self,
        node: Union[pytest.Item, pytest.Collector],
        call: pytest.CallInfo[object],
        report: Union[pytest.CollectReport, pytest.TestReport],
    ) -> None:
        """Reformat the failure representation if the exception is a papermill.PapermillExecutionError."""
        if not (isinstance(report, pytest.TestReport) and JupyterNotebookDiscoverer.is_managed_function(node)):
            return

        if call.when != "call":
            return

        excinfo: Optional[pytest.ExceptionInfo[BaseException]] = call.excinfo
        if excinfo is None or not isinstance(excinfo.value, pm.PapermillExecutionError):
            return

        exc: pm.PapermillExecutionError = excinfo.value

        report.longrepr = "\n".join(exc.traceback)

        # Path in nodeid is relative (shorter + more consistent with rest of pytest output)
        node_path = node.nodeid.split("::", maxsplit=1)[0]

        report.longrepr += f"\n\n{node_path}:cell {exc.cell_index + 1}: {exc.ename}"
