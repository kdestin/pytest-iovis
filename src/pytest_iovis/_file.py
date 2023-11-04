import types
from typing import TYPE_CHECKING, Callable, List, Optional, cast

import pytest
from typing_extensions import Self

if TYPE_CHECKING:
    from _pytest.nodes import Node


class JupyterNotebookFile(pytest.Module):
    """A collector for Jupyter Notebooks.

    Subclasses pytest.Module to leverage pytest features that are baked into the python implementation (e.g.
    parameterization)
    """

    def __init__(self, *args: object, test_functions: List[Callable[..., object]], **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._test_functions = test_functions
        """The test functions to generate for the collected notebook."""

    def _getobj(self) -> types.ModuleType:
        """Get the underlying Python object.

        .. note::

            This is override is necessary but somewhat fragile, since `_getobj` is not part of pytest.Module's public
            api. Collectors in _pytest.python use _getobj to fetch an instance of the actual object they represent
            (Package, Module, Class, Function, etc...).

            The returned module is dynamically built, populated with provided test functions. It then participates in
            pytest's normal collection process for Python test functions. Which allows us to fully leverage features
            like parametrization and fixtures.
        """
        module = types.ModuleType(name="jupyter_notebook_collector")

        for f in self._test_functions:
            # Need to add test functions to the module since pytest tries to access them
            setattr(module, f.__name__, f)

        # Apply the notebook mark to all test functions in the module
        module.pytestmark = pytest.mark.notebook(self.path)  # type: ignore[attr-defined]

        return module


class JupyterNotebookTestFunction(pytest.Function):
    @classmethod
    def from_function(cls, parent: Optional["Node"], other: pytest.Function) -> Self:
        """Create a JupyterNotebookTestFunction as a copy of a pytest.Function.

        :param pytest.Collector parent: The pytest.Collector to set as the parent.
        :param pytest.Function other: The pytest.Function to copy fields from.
        :return: A JupyterNotebookTestFunction
        :rtype: JupyterNotebookTestFunction
        """
        item = cast(
            Self,
            cls.from_parent(  # type: ignore[no-untyped-call]
                name=other.name,
                parent=parent,
                callobj=other.obj,
                callspec=getattr(other, "callspec", None),
                # Accessing private attribute, but parametrization breaks without it
                fixtureinfo=other._fixtureinfo,
                keywords=other.keywords,
                originalname=other.originalname,
            ),
        )

        item.stash = other.stash
        return item
