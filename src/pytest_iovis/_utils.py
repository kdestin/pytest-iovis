import inspect
import re
from typing import TYPE_CHECKING, Any, Callable, Iterable, List, Optional, Tuple, TypeVar, Union, overload

import pytest
from typing_extensions import TypeGuard

if TYPE_CHECKING:
    from _pytest.nodes import Node

T = TypeVar("T")
T2 = TypeVar("T2")


def make_mark_description(mark_fn: Callable[..., object]) -> str:
    """Generate a string that can be used to programmatically register a pytest marker from a function.

    .. example::

        def marker_name(arg1, arg2, arg3) -> None:
            '''Hello World'''

        def pytest_configure(config):
            # "marker_name(arg1, arg2, arg3): Hello World"
            config.addinivalue_line("markers", make_mark_description(notebook))

    :param types.FunctionType c: A function used to generate the marker string. The function name is used as the
        marker name, and the summary line (text before the first blank line) is used as description.
    :returns: A pytest marker definition string
    :rtype: str
    """

    def get_short_description() -> str:
        doc: Optional[str] = inspect.getdoc(mark_fn)

        if doc is None:
            return ""

        # Get the short description, which is the text before the first blankline
        short_description = re.split(r"^\s*$", doc, flags=re.MULTILINE, maxsplit=1)[0]

        # Normalize any endlines into a single line
        return re.sub("\s*\n\s*", " ", short_description).strip()

    name = getattr(mark_fn, "__name__", None)
    if name is None:
        raise ValueError(f"{mark_fn!r} does not have attribute __name__")

    signature_without_return = inspect.signature(mark_fn).replace(return_annotation=inspect.Signature.empty)
    return f"{name}{signature_without_return}: {get_short_description()}"


def error_message_at_node(e: Union[str, Exception], node: "Node") -> str:
    """Add node's location to an exception message.

    :param Union[str,Exception] e: The error message or exception to format
    :param Node node: The pytest node responsible for the error message
    :return: A error message prefixed with locating information about the node
    :rtype: str
    """
    return f"{node.nodeid}: {e}"


def error_message_at_mark_owner(e: Union[str, Exception], node: "Node", mark: pytest.Mark) -> str:
    """Add the owner of a mark's location to an exception message.

    :param Union[str,Exception] e: The error message or exception to format
    :param Node node: A pytest item
    :param pytest.Mark mark: The mark responsible for the error message
    :return: A error message prefixed with locating information about the node that owns the mark
    :rtype: str
    """
    if mark not in node.iter_markers(name=mark.name):
        raise ValueError(f"Mark '{mark.name}' is not applied to '{node.nodeid}'")

    return error_message_at_node(e, next((p for p in node.listchain() if mark in p.own_markers), node))


@overload
def partition(iis: Iterable[T], predicate: Callable[[T], TypeGuard[T2]]) -> Tuple[List[T2], List[T]]:
    ...


@overload
def partition(iis: Iterable[T], predicate: Callable[[T], bool]) -> Tuple[List[T], List[T]]:
    ...


def partition(
    iis: Iterable[T], predicate: Union[Callable[[T], bool], Callable[[T], TypeGuard[T2]]]
) -> Tuple[List[Any], List[T]]:
    """Partition a list of objects into a list of objects that satisfy the predicate, and a list that don't.

    :param Iterable[T] iis: An iterable of objects
    :param predicate: The predicate to apply to the objects in the iterable
    :type predicate: Callable[[T], bool]
    :return: A 2-tuple where:
      * The first item is a list of objects that satisfy the predicate
      * The second item is a list of objects that don't satisfy the predicate
    :rtype: Tuple[List[T], List[T]]
    """
    yes: List[T] = []
    no: List[T] = []

    for i in iis:
        (yes if predicate(i) else no).append(i)

    return yes, no
