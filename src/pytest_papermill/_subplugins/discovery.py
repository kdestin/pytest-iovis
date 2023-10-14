from pathlib import Path
from typing import Callable, List, Optional, cast

import pytest
from typing_extensions import TypeAlias

from .._file import JupyterNotebookFile, test_notebook_runs

T_OpaqueCallable: TypeAlias = Callable[..., object]
"""A type alias for a callable with opaque types (vs Any)."""


class JupyterNotebookDiscoverer:
    """A pytest plugin that enables auto-discovery of Jupyter notebooks as pytest tests"""

    TEST_FUNCTION_KEY = pytest.StashKey[List[T_OpaqueCallable]]()
    """A stash key that stores callables used as test functions for collected notebooks. Meant to be used on config."""

    @classmethod
    def register_default_test_functions(cls, *funcs: T_OpaqueCallable, config: pytest.Config) -> None:
        """Register test functions to be used for collected notebooks.

        May be called multiple times, which adds to previously registered functions.

        :param Callable *funcs: Callables to use as test functions. Must have a __name__ parameter.
        :keyword pytest.Config config: The session's config.
        """
        test_functions = config.stash.setdefault(cls.TEST_FUNCTION_KEY, cast(List[T_OpaqueCallable], []))
        for f in funcs:
            if not callable(f):
                raise ValueError(f"{f!r} is not callable")
            if getattr(f, "__name__", None) is None:
                raise ValueError(f"{f!r} does not have a __name__")

            test_functions.append(f)

    def pytest_collect_file(self, file_path: Path, parent: pytest.Collector) -> Optional[pytest.Collector]:
        """Make pytest.Collectors for Jupyter Notebooks"""
        if file_path.suffix in [".ipynb"]:
            return JupyterNotebookFile.from_parent(
                parent,
                path=file_path,
                test_functions=parent.config.stash.get(self.TEST_FUNCTION_KEY, [test_notebook_runs]),
            )
        return None


register_default_test_functions = JupyterNotebookDiscoverer.register_default_test_functions
