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
):
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
