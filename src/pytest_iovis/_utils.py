import enum
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Iterable, List, Optional, Tuple, Type, TypeVar, Union, cast, overload

from typing_extensions import Self, TypeGuard

from ._types import PathType

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


class PathTrie(Generic[T]):
    """A trie that accepts the parts (i.e `Path.parts`) of an absolute path, and stores some associated payload."""

    class NoPayload:
        """A distinct type used to signify that a PathTrie Node has no payload."""

    @dataclass
    class Node(Generic[T2]):
        """A Node of a PathTrie that can store a generic payload."""

        payload: Union[T2, Type["PathTrie.NoPayload"]] = field(default_factory=lambda: PathTrie.NoPayload)
        children: Dict[str, Self] = field(default_factory=dict)

    class InsertType(enum.Enum):
        LEAF = enum.auto()
        """Whether the inserted path is not a prefix of another value in the trie."""
        PREFIX = enum.auto()
        """Whether the inserted path is a prefix of another value in the trie."""

    def __init__(self, root_payload: T) -> None:
        self.root: PathTrie.Node[T] = PathTrie.Node(payload=root_payload)

    @staticmethod
    def _normalize(p: PathType) -> Path:
        """Normalize the path argument."""
        return Path(p).resolve()

    def __contains__(self, obj: object) -> bool:
        """Return whether the PathTrie has a payload for the given object."""
        if not isinstance(obj, (str, os.PathLike)):
            return False

        curr = self.root

        for part in self._normalize(obj).parts:
            if part not in curr.children:
                return False
            curr = curr.children[part]

        return curr.payload is not PathTrie.NoPayload

    def insert(self, p: Optional[PathType], payload: T) -> "PathTrie.InsertType":
        """Insert a payload for a given path.

        :param Optional[PathType] p: The path to insert. If `None`, will insert at root
        :param T payload: The payload to store
        :returns: Whether or not the inserted path is the prefix of another path in the trie.
        :rtype: InsertType
        """
        curr = self.root
        insert_type = PathTrie.InsertType.PREFIX

        for part in self._normalize(p).parts if p is not None else ():
            if part not in curr.children:
                insert_type = PathTrie.InsertType.LEAF
            curr = curr.children.setdefault(part, PathTrie.Node())

        curr.payload = payload
        return insert_type

    def longest_common_prefix(self, p: PathType) -> T:
        """Retrieve the payload of the longest matching prefix of the argument present in the trie.

        This method is guaranteed to always return a result, since the root node always has a payload.

        :param Optional[PathType] p: The path to find the longest common prefix of.
        :returns: The payload of the longest common prefix
        :rtype: T
        """
        curr = self.root
        result = self.root.payload
        assert result is not PathTrie.NoPayload, "root node should always have a valid payload"

        for part in self._normalize(p).parts:
            if part not in curr.children:
                break

            curr = curr.children[part]

            if curr.payload is not PathTrie.NoPayload:
                result = curr.payload

        return cast(T, result)
