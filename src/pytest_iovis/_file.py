import types
from typing import List

import pytest

from ._types import TestObject


class JupyterNotebookFile(pytest.Module):
    """A collector for Jupyter Notebooks.

    Subclasses pytest.Module to leverage pytest features that are baked into the python implementation (e.g.
    parameterization)
    """

    def __init__(self, *args: object, test_functions: List[TestObject], **kwargs: object) -> None:
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

        return module
