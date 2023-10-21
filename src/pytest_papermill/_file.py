import types
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Union, cast

import papermill as pm
import pytest
from nbformat import NotebookNode

if TYPE_CHECKING:
    from _pytest._code.code import TerminalRepr
    from _pytest.nodes import Node


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


class JupyterNotebookFile(pytest.Module):
    """A collector for Jupyter Notebooks.

    Subclasses pytest.Module to leverage pytest features that are baked into the python implementation (e.g.
    parameterization)
    """

    def __init__(self, *args: object, test_functions: List[Callable[..., object]], **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._test_functions = test_functions
        """The test functions to generate for the collected notebook."""

    def collect(self) -> Iterable[pytest.Function]:
        """Collect children pytest.Items for this collector."""
        for f in self._test_functions:
            yield from self.ihook.pytest_pycollect_makeitem(collector=self, name=f.__name__, obj=f) or []

    def _getobj(self) -> types.ModuleType:
        """Get the underlying Python object.

        .. note::

            This is override is necessary but somewhat fragile, since `_getobj` is not part of pytest.Module's public
            api. Collectors in _pytest.python use _getobj to fetch an instance of the actual object they represent
            (Package, Module, Class, Function, etc...).
        """
        module = types.ModuleType(name="jupyter_notebook_collector")

        for f in self._test_functions:
            # Need to add test functions to the module since pytest tries to access them
            setattr(module, f.__name__, f)

        # Apply the notebook mark to all test functions in the module
        module.pytestmark = pytest.mark.notebook(self.path)  # type: ignore[attr-defined]

        return module


class JupyterNotebookTestFunction(pytest.Function):
    def repr_failure(  # type: ignore[override]
        self, excinfo: pytest.ExceptionInfo[BaseException]
    ) -> Union[str, "TerminalRepr"]:
        """Return a representation of a test failure.

        :param excinfo: Exception information for the failure.
        :returns: The formatted exception
        :rtype: str or _pytest._code.code.TerminalRepr
        """
        if isinstance(excinfo.value, pm.PapermillExecutionError):
            return "\n".join(excinfo.value.traceback)
        return super().repr_failure(excinfo)

    @classmethod
    def from_function(cls, parent: Optional["Node"], other: pytest.Function) -> "JupyterNotebookTestFunction":
        """Create a JupyterNotebookTestFunction as a copy of a pytest.Function.

        :param pytest.Collector parent: The pytest.Collector to set as the parent.
        :param pytest.Function other: The pytest.Function to copy fields from.
        :return: A JupyterNotebookTestFunction
        :rtype: JupyterNotebookTestFunction
        """
        item = cls.from_parent(
            name=other.name,
            parent=parent,
            callobj=other.obj,
            callspec=getattr(other, "callspec", None),
            # Accessing private attribute, but parametrization breaks without it
            fixtureinfo=other._fixtureinfo,
            keywords=other.keywords,
            originalname=other.originalname,
        )

        item.stash = other.stash
        return item
