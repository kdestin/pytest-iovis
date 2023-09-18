from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import papermill as pm
import pytest

from . import _fixtures
from ._subplugins import IPythonMarkupPlugin


def pytest_configure(config: pytest.Config):
    config.pluginmanager.register(_fixtures)
    config.pluginmanager.register(IPythonMarkupPlugin())


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> Optional[pytest.Collector]:
    if file_path.suffix in [".ipynb"]:
        return JupyterNotebookFile.from_parent(parent, path=file_path)
    return None


class JupyterNotebookFile(pytest.File):
    def collect(self):
        yield JupyterNotebookTestFunction.from_parent(
            parent=self,
            name=run_note_book.__name__,
            callobj=run_note_book,
        )


class JupyterNotebookTestFunction(pytest.Function):
    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException]):
        if isinstance(excinfo.value, pm.PapermillExecutionError):
            return "\n".join(excinfo.value.traceback)
        return super().repr_failure(excinfo)


def run_note_book(
    notebook_path: Path,
    notebook_output_path: Path,
    notebook_parameters: Dict[str, Any],
    notebook_extra_arguments: Iterable[str],
):
    pm.execute_notebook(
        notebook_path,
        notebook_output_path,
        parameters=notebook_parameters,
        extra_arguments=list(notebook_extra_arguments),
    )
