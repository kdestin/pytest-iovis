import os
from typing import Any, Callable, Iterable, Optional, Protocol, Tuple, Type, Union

from typing_extensions import TypeAlias


class NamedCallable(Protocol):
    """A callable that has a name.

    .. example::

        def foo():
            pass
    """

    __name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        pass


TestObject: TypeAlias = Union[NamedCallable, Type[object]]
"""A object that pytest can collect as a test."""


PathType: TypeAlias = Union[str, "os.PathLike[str]"]


class FileTestFunctionCallback(Protocol):
    """The type of the user-provided callable used to specify tests for a single file."""

    def __call__(
        self,
        *,
        inherited: Tuple[TestObject, ...],
    ) -> Iterable[TestObject]:
        raise NotImplementedError()


class SetTestFunctionHook(Protocol):
    """The type of the pytest_iovis_set_tests hook."""

    def __call__(
        self,
        *,
        inherited: Tuple[TestObject, ...],
        tests_for: Callable[[PathType], Callable[[FileTestFunctionCallback], None]],
    ) -> Optional[Iterable[TestObject]]:
        raise NotImplementedError()
