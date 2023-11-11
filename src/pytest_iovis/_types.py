from typing import Any, Protocol, Type, Union

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
