from typing import Any, Callable, Iterable, List, Tuple, TypeVar, Union, overload

from typing_extensions import TypeGuard

T = TypeVar("T")
T2 = TypeVar("T2")


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
