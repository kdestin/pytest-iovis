from pathlib import Path
from typing import Any, Dict, Iterable, cast

import papermill as pm
import pytest
from nbformat import NotebookNode


def run_note_book(
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


class JupyterNotebookFile(pytest.File):
    def collect(self) -> Iterable[pytest.Function]:
        """Collect children pytest.Items for this collector

        Return default auto-generated test function(s) for a notebook.
        """
        yield JupyterNotebookTestFunction.from_parent(
            parent=self,
            name=run_note_book.__name__,
            callobj=run_note_book,
        )


class JupyterNotebookTestFunction(pytest.Function):
    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException]) -> str:
        """Return a representation of a test failure.

        :param excinfo: Exception information for the failure.
        :returns: The formatted exception
        :rtype: str or _pytest._code.code.TerminalRepr
        """
        if isinstance(excinfo.value, pm.PapermillExecutionError):
            return "\n".join(excinfo.value.traceback)
        return super().repr_failure(excinfo)
