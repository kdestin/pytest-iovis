import contextlib
import heapq
import os
import types
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

import pluggy
import pytest
from typing_extensions import Self, TypeAlias, TypeGuard

from .._file import JupyterNotebookFile
from .._utils import partition

T_OpaqueCallable: TypeAlias = Callable[..., object]
"""A type alias for a callable with opaque types (vs Any)."""
T_File = TypeVar("T_File", bound=pytest.File)
T = TypeVar("T")

TestObject = Union[Type[object], T_OpaqueCallable]


@dataclass
class NotebookPathArg:
    """A thin wrapper around a pathlib.Path.

    Allows to ensure that we're generating an id for the correct value in pytest_make_parametrize_id.
    """

    path: Path
    """The absolute path to the file."""


class FileDelayer(Generic[T_File]):
    """Delays Collection of a pytest.File collectors until other collectors have been collected."""

    def __init__(self, collector_type: Type[T_File]) -> None:
        self._file_collector_type: Type[T_File] = collector_type
        """The collector type to delay"""
        self._DELAYED_KEY = pytest.StashKey[List[T_File]]()
        """Key that maps to a list of delayed collectors. Should be used on a session stash."""

        self._REMAINING_CALLS_KEY = pytest.StashKey[int]()
        """Key that maps to the expected remaining number of calls of pytest_make_collect_report with a
        pytest.File argument. Should be used on a session stash.
        """

        self._IS_COLLECTING = pytest.StashKey[bool]()
        """Key that maps to a bool which is set to True if pytest doing test collection as part of its documented
        collection protocol (i.e. pytest_collection has been called)."""

    def is_last_make_collect_report_for_file(self, session: pytest.Session) -> bool:
        """Whether this is the last pytest_make_collect_report hook called on a pytest.File.

        Should only be called within pytest_make_collect_report_hook
        """
        return session.stash.get(self._REMAINING_CALLS_KEY, None) == 0

    def remove_delayed(self, report: pytest.CollectReport, delayed_collectors: List[T_File]) -> None:
        """Remove delayed collectors from pytest.CollectReport.

        :param pytest.CollectReport report: The pytest.CollectReport to modify
        :param List[T_File] delayed_collectors: The current list of delayed collectors. Will be modified in place.
        """

        def is_file_collector(item: Union[pytest.Item, pytest.Collector]) -> TypeGuard[T_File]:
            return isinstance(item, self._file_collector_type)

        new_delayed_collectors, report.result = partition(report.result, is_file_collector)

        delayed_collectors.extend(new_delayed_collectors)

    def add_delayed(self, report: pytest.CollectReport, delayed_collectors: List[T_File]) -> None:
        """Add delayed collectors to pytest.CollectReport. Stored collectors are cleared.

        :param pytest.CollectReport report: The pytest.CollectReport to modify
        :param List[T_File] delayed_collectors: The current list of delayed collectors. Will be cleared.
        """
        report.result.extend(delayed_collectors)
        delayed_collectors.clear()

    def get_delayed(self, session: pytest.Session) -> List[T_File]:
        return session.stash[self._DELAYED_KEY]

    def is_pytest_collecting(self, session: pytest.Session) -> bool:
        """Return whether pytest_collection has been called.

        This to differentiate when a call to a collection related hook is part of the normal collection protocol,
        or directly as part of something like `pytest --fixtures`.
        """
        return session.stash.get(self._IS_COLLECTING, False) is True

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection(self, session: pytest.Session) -> Iterable[None]:
        """Initialize session variables."""
        session.stash[self._DELAYED_KEY] = cast(List[T_File], [])
        session.stash[self._REMAINING_CALLS_KEY] = 1  # Start at 1 since collect is always called on the session itself
        session.stash[self._IS_COLLECTING] = True

        yield

        del session.stash[self._IS_COLLECTING]
        del session.stash[self._DELAYED_KEY]
        del session.stash[self._REMAINING_CALLS_KEY]

    @pytest.hookimpl(hookwrapper=True)
    def pytest_make_collect_report(
        self, collector: pytest.Collector
    ) -> Generator[None, pluggy.Result[pytest.CollectReport], None]:
        result: pluggy.Result[pytest.CollectReport] = yield

        session = collector.session

        if not self.is_pytest_collecting(session):
            return

        if isinstance(collector, self._file_collector_type):
            return

        report = result.get_result()
        delayed_collectors = self.get_delayed(session)

        if isinstance(collector, (pytest.Session, pytest.File)):
            session.stash[self._REMAINING_CALLS_KEY] -= 1

        self.remove_delayed(report, delayed_collectors)

        # This hook will be called once for every collected file
        session.stash[self._REMAINING_CALLS_KEY] += sum(isinstance(r, pytest.File) for r in report.result)


class SetDefaultForFileHookFunction(Protocol):
    def __call__(
        self,
        *,
        inherited: Tuple[TestObject, ...],
    ) -> Iterable[TestObject]:
        raise NotImplementedError()


class SetDefaultHookFunction(Protocol):
    """The type of the pytest_iovis_set_default_function hook."""

    def __call__(
        self,
        *,
        inherited: Tuple[TestObject, ...],
        for_notebook: Callable[[Union[str, "os.PathLike[str]"]], Callable[[SetDefaultForFileHookFunction], None]],
    ) -> Optional[Iterable[TestObject]]:
        raise NotImplementedError()


class NoPayload:
    """A distinct type used to signify that a PathTrie Node has no payload."""


@dataclass
class Node(Generic[T]):
    """A Node of a PathTrie that can store a generic payload."""

    payload: Union[T, Type[NoPayload]] = NoPayload
    children: Dict[str, Self] = field(default_factory=dict)


class PathTrie(Generic[T]):
    """A trie that accepts the parts (i.e `Path.parts`) of an absolute path, and stores some associated payload."""

    def __init__(self, root_payload: T) -> None:
        self.root: Node[T] = Node(payload=root_payload)

    @staticmethod
    def _normalize(p: Union[str, "os.PathLike[str]"]) -> Path:
        """Normalize the path argument."""
        return Path(p).resolve()

    def insert(self, p: Optional[Union[str, "os.PathLike[str]"]], payload: T) -> None:
        """Insert a payload for a given path.

        :param p: The path to insert. If `None`, will insert at root
        :type p: Optional[Union[str, "os.PathLike[str]"]]
        :param T payload: The payload to store
        """
        curr = self.root

        for part in self._normalize(p).parts if p is not None else ():
            curr = curr.children.setdefault(part, Node())

        curr.payload = payload

    def longest_common_prefix(self, p: Union[str, "os.PathLike[str]"]) -> T:
        """Retrieve the payload of the longest matching prefix of the argument present in the trie.

        This method is guaranteed to always return a result, since the root node always has a payload.

        :param p: The path to find the longest common prefix of.
        :type p: Optional[Union[str, "os.PathLike[str]"]]
        :returns: The payload of the longest common prefix
        :rtype: T
        """
        curr = self.root
        result = self.root.payload
        assert result is not NoPayload, "root node should always have a valid payload"

        for part in self._normalize(p).parts:
            if part not in curr.children:
                break

            curr = curr.children[part]

            if curr.payload is not NoPayload:
                result = curr.payload

        return cast(T, result)


class TestFunctionManager:
    __DEFAULT_FUNCTION_RESOLVERS = pytest.StashKey[List[SetDefaultHookFunction]]()
    __PATH_TRIE = pytest.StashKey[PathTrie[Tuple[TestObject, ...]]]()

    def pytest_addhooks(self, pluginmanager: pytest.PytestPluginManager) -> None:
        """Register the `pytest_iovis_set_default_functions` hook."""

        class HookSpec:
            @pytest.hookspec(firstresult=True)
            def pytest_iovis_set_default_functions(
                self,
                inherited: Tuple[TestObject, ...],
                for_notebook: Callable[
                    [Union[str, "os.PathLike[str]"]], Callable[[SetDefaultForFileHookFunction], None]
                ],
            ) -> Optional[Iterable[TestObject]]:
                """Set the default test functions for collected Jupyter Notebooks.

                The defaults returned by this hook apply to all collected notebooks under the parent directory this is
                called from.

                This hook will only be called when found in `conftest.py`.

                :param inherited: The test functions inherited from a higher scope
                :type inherited: Tuple[TestObject, ...]
                :return: Either:
                    * A iterable of test functions that will be used for all collected notebooks
                    * None, which is equivalent to this hook not having been called
                :rtype: Optional[Iterable[TestObject]]
                """
                raise NotImplementedError()

        # Useless assignment so that mypy ensures the hook implements protocol
        _: SetDefaultHookFunction = HookSpec().pytest_iovis_set_default_functions

        pluginmanager.add_hookspecs(HookSpec)

    @staticmethod
    def is_conftest(obj: object) -> TypeGuard[types.ModuleType]:
        return isinstance(obj, types.ModuleType) and Path(obj.__file__ or ".").name == "conftest.py"

    @contextlib.contextmanager
    def with_populated_trie(self, session: pytest.Session) -> Iterator[None]:
        """Build a path trie that can be used to compute test functions for a scope.

        The path trie is made available for the interior scope of the context manager.

        :param pytest.Session session: The pytest session
        """

        def call_hook_without(plugins: Iterable[object]) -> SetDefaultHookFunction:
            """Return the hook function that runs on all plugins except the supplied ones."""
            return manager.subset_hook_caller("pytest_iovis_set_default_functions", remove_plugins=plugins)

        class ScopedHook(NamedTuple):
            path: Path
            hook: SetDefaultHookFunction

        def make_register_fn(
            confdir: Path, scoped_confs_heap: List[ScopedHook], empty_hook_caller: pluggy.HookCaller
        ) -> Callable[[Union[str, "os.PathLike[str]"]], Callable[[SetDefaultForFileHookFunction], None]]:
            def for_notebook(path: Union[str, "os.PathLike[str]"]) -> Callable[[SetDefaultForFileHookFunction], None]:
                pathlib_path = Path(path).resolve()
                assert confdir in pathlib_path.parents
                assert pathlib_path.is_file()

                def decorator(f: SetDefaultForFileHookFunction) -> None:
                    def pytest_iovis_set_default_functions(
                        inherited: Tuple[TestObject, ...], for_notebook: object  # noqa: ARG001
                    ) -> Iterable[TestObject]:
                        return cast(Iterable[TestObject], empty_hook_caller.call_extra([f], {"inherited": inherited}))

                    heapq.heappush(
                        scoped_confs_heap, ScopedHook(path=pathlib_path, hook=pytest_iovis_set_default_functions)
                    )

                return decorator

            return for_notebook

        def build_payloads(
            confs: Iterable[types.ModuleType], default: Tuple[TestObject, ...]
        ) -> Iterable[Tuple[Path, Tuple[TestObject, ...]]]:
            """Return an iterable of tuples suitable to be unpacked as arguments to PathTrie.insert.

            Performs a pre-order traversal on conftest plugins based on their location in the filesystem tree to
            accumulate the test functions specified by those conftests.

            :param Iterable[types.ModuleType] confs: The conftest modules
            :param Tuple[TestObject,...] default: The root payload
            """
            scoped_confs = [
                ScopedHook(
                    path=Path(conftest.__file__).parent, hook=call_hook_without(all_plugins.difference({conftest}))
                )
                for conftest in confs
                if conftest.__file__
            ]

            # Ensure that scoped hooks are ordered as if we did a pre-order traversal (which happens with pathlib's
            # default comparator).
            heapq.heapify(scoped_confs)

            def _build_payloads_impl(
                prev: Optional[Path], curr_objs: Tuple[TestObject, ...]
            ) -> Iterable[Tuple[Path, Tuple[TestObject, ...]]]:
                while scoped_confs:
                    root = scoped_confs[0]

                    if prev is not None and prev not in root.path.parents:
                        return

                    heapq.heappop(scoped_confs)
                    result = root.hook(
                        inherited=curr_objs, for_notebook=make_register_fn(root.path, scoped_confs, empty_hook_caller)
                    )

                    if result is None:
                        continue

                    funcs = tuple(result)
                    yield (root.path, funcs)
                    yield from _build_payloads_impl(root.path, funcs)

            yield from _build_payloads_impl(None, (default))

        manager = session.config.pluginmanager

        all_plugins = manager.get_plugins()
        empty_hook_caller: pluggy.HookCaller = manager.subset_hook_caller(
            "pytest_iovis_set_default_functions", all_plugins
        )
        conftest_plugins, non_conftest_plugins = partition(all_plugins, self.is_conftest)

        non_conftest_hooks = call_hook_without(conftest_plugins)
        result = non_conftest_hooks(inherited=(), for_notebook=lambda _: lambda _: None)

        global_test_functions = tuple(result or ())

        path_trie = PathTrie(root_payload=global_test_functions)

        for path, payload in build_payloads(conftest_plugins, default=global_test_functions):
            path_trie.insert(path, payload)

        session.stash[self.__PATH_TRIE] = path_trie

        yield

        del session.stash[self.__PATH_TRIE]

    def test_functions_for(self, session: pytest.Session, p: Union[str, "os.PathLike[str]"]) -> Iterable[TestObject]:
        """Compute the test functions that are in-scope at a given path.

        This function should be called within TestFunctionManager.with_populated_trie.


        :param pytest.Session session: The pytest session
        :param p: The path to find tests for.
        :type p: Optional[Union[str, "os.PathLike[str]"]]
        :returns: A list of tests
        :rtype: Iterable[TestObject]
        """
        path_trie = session.stash.get(self.__PATH_TRIE, None)

        if path_trie is None:
            return []

        return path_trie.longest_common_prefix(p)


class JupyterNotebookDiscoverer:
    """A pytest plugin that enables auto-discovery of Jupyter notebooks as pytest tests."""

    PLUGIN_NAME = "notebook_discovery"
    """A user facing name that describes this plugin."""
    __DELAYER_NAME = "jupyter_notebook_file_delayer"
    __FUNCTION_MANAGER_KEY = pytest.StashKey[TestFunctionManager]()
    FIXTURE_NAME = "notebook_path"
    """The name of the fixture that will be parametrized by this plugin"""

    __PLACEHOLDER_NOTEBOOK_PARAMSET_ID = f"{uuid.uuid4()}{uuid.uuid4()}"

    @pytest.hookimpl(trylast=True)
    def pytest_iovis_set_default_functions(self) -> Iterable[T_OpaqueCallable]:
        def test_nothing(notebook_path: Path) -> None:  # noqa: ARG001
            """Do nothing."""

        yield test_nothing

    def get_delayer(self, session: pytest.Session) -> FileDelayer[JupyterNotebookFile]:
        """Retrieve the FileDelayer plugin used to delay JupyterNotebookFile collectors."""
        plugin = session.config.pluginmanager.get_plugin(self.__DELAYER_NAME)
        if plugin is None:
            raise ValueError("Plugin was not registered")
        return cast(FileDelayer[JupyterNotebookFile], plugin)

    def pytest_configure(self, config: pytest.Config) -> None:
        """Register a plugin that delays the collection of JupyterNotebookFiles until after every other file."""
        config.pluginmanager.register(FileDelayer(JupyterNotebookFile), name=self.__DELAYER_NAME)

        function_manager = TestFunctionManager()
        config.pluginmanager.register(function_manager)
        config.stash[self.__FUNCTION_MANAGER_KEY] = function_manager

    def pytest_collect_file(self, file_path: Path, parent: pytest.Collector) -> Optional[pytest.Collector]:
        """Make pytest.Collectors for Jupyter Notebooks."""
        if file_path.suffix in [".ipynb"]:
            return cast(
                JupyterNotebookFile,
                JupyterNotebookFile.from_parent(
                    parent,
                    path=file_path,
                    # Will be populated later
                    test_functions=[],
                ),
            )
        return None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_make_collect_report(
        self, collector: pytest.Collector
    ) -> Generator[None, pluggy.Result[pytest.CollectReport], None]:
        """Remove JupyterNotebookFile collectors that don't need to be collected.

        The JupyterNotebookFile collectors created by this class are unneeded if the user has written at least one
        test function for the collected file. This function delays the collection of JupyterNotebookFiles so that
        unneeded collectors can be removed.
        """
        result: pluggy.Result[pytest.CollectReport] = yield

        if isinstance(collector, JupyterNotebookFile):
            return

        report = result.get_result()
        session = collector.session
        delayer = self.get_delayer(session)
        func_manager = session.config.stash[self.__FUNCTION_MANAGER_KEY]

        if not delayer.is_pytest_collecting(session):
            return

        if delayer.is_last_make_collect_report_for_file(session):
            delayed_collectors = delayer.get_delayed(session)

            # Compute test functions based on collector path
            with func_manager.with_populated_trie(session):
                for c in delayed_collectors:
                    c.test_functions = list(func_manager.test_functions_for(session, c.path))

            # Queue the collectors for collection
            delayer.add_delayed(report, delayed_collectors)

    @classmethod
    def is_managed_function(cls, item: Union[pytest.Item, pytest.Collector]) -> TypeGuard[pytest.Function]:
        """Check whether the pytest.Item is a pytest.Function that is managed by this plugin."""
        return isinstance(item, pytest.Function) and item.getparent(JupyterNotebookFile) is not None

    @classmethod
    def get_notebook_path(cls, item: Union[pytest.Item, pytest.Collector]) -> Optional[Path]:
        """Get the notebook path associated with a test function."""
        isParameterizedFunction = isinstance(item, pytest.Function) and hasattr(item, "callspec")

        if not isParameterizedFunction:
            return None

        if not cls.is_managed_function(item):
            return None

        try:
            args = cast(NotebookPathArg, item.callspec.getparam(cls.FIXTURE_NAME))
            return args.path
        except ValueError:
            return None

    def pytest_make_parametrize_id(self, val: object, argname: str) -> Optional[str]:
        """Return a placeholder ID when parametrizing on the notebook path fixture that can be later removed."""
        if not (isinstance(val, NotebookPathArg) and argname == self.FIXTURE_NAME):
            return None

        return self.__PLACEHOLDER_NOTEBOOK_PARAMSET_ID

    def pytest_generate_tests(self, metafunc: pytest.Metafunc) -> None:
        """Parametrize the `notebook_path` fixture to associate each test function with the notebook path."""
        if not self.is_managed_function(metafunc.definition):
            return

        parent = metafunc.definition.getparent(JupyterNotebookFile)
        assert parent is not None
        # Indirect Parameterization allow's for the user's input to be used as the test ID, and delay resolving it
        # to a user's input to a pathlib.Path until right before the fixture actually produces a value.
        metafunc.parametrize(self.FIXTURE_NAME, [NotebookPathArg(path=parent.path)], indirect=True)

        # Remove our placeholder ID from the ID list
        for c in metafunc._calls:
            c._idlist[:] = [s for s in c._idlist if not s.startswith(self.__PLACEHOLDER_NOTEBOOK_PARAMSET_ID)]

    def pytest_collection_modifyitems(self, items: List[pytest.Item]) -> None:
        """Remove empty parametrization brackets."""
        for item in items:
            # Remove empty parameterization brackets
            if self.is_managed_function(item) and item.name.endswith("[]"):
                item.name = item.name[:-2]
                item._nodeid = item._nodeid[:-2]
