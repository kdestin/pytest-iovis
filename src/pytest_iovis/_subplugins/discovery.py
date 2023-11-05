import enum
import os
import types
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Generic, Iterable, List, Optional, Protocol, Tuple, Type, TypeVar, Union, cast

import pytest
from typing_extensions import Self, TypeAlias, TypeGuard

from .._file import JupyterNotebookFile
from .._utils import partition

T_OpaqueCallable: TypeAlias = Callable[..., object]
"""A type alias for a callable with opaque types (vs Any)."""
T = TypeVar("T")

TestObject = Union[Type[object], T_OpaqueCallable]


@dataclass
class NotebookPathArg:
    """A thin wrapper around a pathlib.Path.

    Allows to ensure that we're generating an id for the correct value in pytest_make_parametrize_id.
    """

    path: Path
    """The absolute path to the file."""


class SetDefaultForFileHookFunction(Protocol):
    """The type of the user-provided callable used to specify tests for a single file."""

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


class InsertType(enum.Enum):
    LEAF = enum.auto()
    """Whether the inserted path is not a prefix of another value in the trie."""
    PREFIX = enum.auto()
    """Whether the inserted path is a prefix of another value in the trie."""


class PathTrie(Generic[T]):
    """A trie that accepts the parts (i.e `Path.parts`) of an absolute path, and stores some associated payload."""

    def __init__(self, root_payload: T) -> None:
        self.root: Node[T] = Node(payload=root_payload)

    @staticmethod
    def _normalize(p: Union[str, "os.PathLike[str]"]) -> Path:
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

        return curr.payload is not NoPayload

    def insert(self, p: Optional[Union[str, "os.PathLike[str]"]], payload: T) -> InsertType:
        """Insert a payload for a given path.

        :param p: The path to insert. If `None`, will insert at root
        :type p: Optional[Union[str, "os.PathLike[str]"]]
        :param T payload: The payload to store
        :returns: Whether or not the inserted path is the prefix of another path in the trie.
        :rtype: InsertType
        """
        curr = self.root
        insert_type = InsertType.PREFIX

        for part in self._normalize(p).parts if p is not None else ():
            if part not in curr.children:
                insert_type = InsertType.LEAF
            curr = curr.children.setdefault(part, Node())

        curr.payload = payload
        return insert_type

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


class ScopedFunctionHandler:
    """A plugin that builds an index that can be used to query which test function to use for a given path.

    .. note::

        This plugin relies on some _technically_ undocumented behavior of pytest.

        `pytest` discovers `conftest.py`'s as it performs collection, registering new ones it finds _as soon_ as it
        descends into a new directory. This ordering is perfect for us, since it means that we can do an online build
        of our index as pytest discovers `conftest.py`'s. And we know that once its time to collect a file that we
        care about, all the relevant conftest.py's are in our index.

    """

    def __init__(self) -> None:
        # Assigning to the instance instead of stashing in a session because the session object isn't available in
        # pytest_plugin_registered.
        self.file_hooks: Dict[Path, SetDefaultHookFunction] = {}
        self.path_trie: Optional[PathTrie[Tuple[TestObject, ...]]] = None

    @pytest.hookimpl(trylast=True)
    def pytest_configure(self, config: pytest.Config) -> None:
        """Initialize our path_trie with the global test functions and any already collected conftest.py."""
        manager = config.pluginmanager
        all_plugins = manager.get_plugins()
        conftest_plugins, non_conftest_plugins = partition(all_plugins, self.is_conftest)

        non_conftest_hooks = self.call_hook_without(manager, conftest_plugins)
        result = non_conftest_hooks(inherited=(), for_notebook=lambda _: lambda _: None)

        global_test_functions = tuple(result or ())

        self.path_trie = PathTrie(root_payload=global_test_functions)
        for conftest in sorted(conftest_plugins, key=lambda c: Path(c.__file__ or "")):
            assert conftest.__file__
            self.add_scoped_hook(
                manager,
                Path(conftest.__file__).parent,
                self.call_hook_without(manager, all_plugins.difference({conftest})),
            )

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

    @staticmethod
    def call_hook_without(manager: pytest.PytestPluginManager, plugins: Iterable[object]) -> SetDefaultHookFunction:
        """Return the hook function that runs on all plugins except the supplied ones."""
        return manager.subset_hook_caller("pytest_iovis_set_default_functions", remove_plugins=plugins)

    def pytest_plugin_registered(self, plugin: object, manager: pytest.PytestPluginManager) -> None:
        if not self.is_conftest(plugin):
            return

        assert plugin.__file__

        self.add_scoped_hook(
            manager,
            Path(plugin.__file__).parent,
            self.call_hook_without(manager, manager.get_plugins().difference({plugin})),
        )

    def add_scoped_hook(self, manager: pytest.PytestPluginManager, scope: Path, hook: SetDefaultHookFunction) -> None:
        """Invoke the hook function for the specified scope, and add the result to our function index.

        :param pytest.PytestPluginManager manager: The pytest plugin manager for the current session
        :param Path scope: The scope the hook applies to
        :param SetDefaultHookFunction hook: The hook function to invoke
        """
        path_trie = self.path_trie
        if path_trie is None:
            return

        if scope in path_trie:
            return

        empty_hook_caller = manager.subset_hook_caller("pytest_iovis_set_default_functions", manager.get_plugins())

        def make_register_fn(
            confdir: Path,
        ) -> Callable[[Union[str, "os.PathLike[str]"]], Callable[[SetDefaultForFileHookFunction], None]]:
            def for_notebook(path: Union[str, "os.PathLike[str]"]) -> Callable[[SetDefaultForFileHookFunction], None]:
                pathlib_path = Path(path) if Path(path).is_absolute() else Path(scope, path).resolve()
                assert confdir in pathlib_path.parents
                assert pathlib_path.is_file(), pathlib_path

                def decorator(f: SetDefaultForFileHookFunction) -> None:
                    def pytest_iovis_set_default_functions(
                        inherited: Tuple[TestObject, ...], for_notebook: object  # noqa: ARG001
                    ) -> Iterable[TestObject]:
                        return cast(
                            Iterable[TestObject],
                            empty_hook_caller.call_extra(
                                [f], {"inherited": inherited, "for_notebook": make_register_fn(pathlib_path)}
                            ),
                        )

                    self.file_hooks[pathlib_path] = pytest_iovis_set_default_functions

                return decorator

            return for_notebook

        current_funcs = self.test_functions_for(scope)
        functions_for_scope = hook(inherited=tuple(current_funcs), for_notebook=make_register_fn(scope))
        if functions_for_scope is None:
            return

        # Sanity check to make sure we're getting scopes that are always more specific
        assert path_trie.insert(scope, tuple(functions_for_scope)) == InsertType.LEAF

    def add_scoped_hook_for_file(self, manager: pytest.PytestPluginManager, path: Path) -> None:
        """Invoke the hook function for the specified scope, and add the result to our function index.

        :param pytest.PytestPluginManager manager: The pytest plugin manager for the current session
        :param Path scope: The scope the hook applies to
        :param SetDefaultHookFunction hook: The hook function to invoke
        """
        assert path.is_file()
        file_hooks = self.file_hooks
        hook = file_hooks.pop(path, None)
        if hook is not None:
            self.add_scoped_hook(manager, scope=path, hook=hook)

    def test_functions_for(self, p: Union[str, "os.PathLike[str]"]) -> Iterable[TestObject]:
        """Compute the test functions that are in-scope at a given path.

        This function should be called within TestFunctionManager.with_populated_trie.


        :param pytest.Session session: The pytest session
        :param p: The path to find tests for.
        :type p: Optional[Union[str, "os.PathLike[str]"]]
        :returns: A list of tests
        :rtype: Iterable[TestObject]
        """
        path_trie = self.path_trie
        return path_trie.longest_common_prefix(p) if path_trie is not None else ()


class JupyterNotebookDiscoverer:
    """A pytest plugin that enables auto-discovery of Jupyter notebooks as pytest tests."""

    PLUGIN_NAME = "notebook_discovery"
    """A user facing name that describes this plugin."""
    __FUNCTION_HANDLER_KEY = pytest.StashKey[ScopedFunctionHandler]()
    """The stash key used to retrieve a ScopedFunctionHandler from the config stash."""
    FIXTURE_NAME = "notebook_path"
    """The name of the fixture that will be parametrized by this plugin"""

    __PLACEHOLDER_NOTEBOOK_PARAMSET_ID = f"{uuid.uuid4()}{uuid.uuid4()}"
    """A placeholder parametrization id for the notebook_path fixture that will later be removed."""

    @pytest.hookimpl(trylast=True)
    def pytest_iovis_set_default_functions(self) -> Iterable[T_OpaqueCallable]:
        def test_nothing(notebook_path: Path) -> None:  # noqa: ARG001
            """Do nothing."""

        yield test_nothing

    def pytest_configure(self, config: pytest.Config) -> None:
        """Register a plugin that can be used to query test functions for a given scope."""
        function_manager = ScopedFunctionHandler()
        config.pluginmanager.register(function_manager)
        config.stash[self.__FUNCTION_HANDLER_KEY] = function_manager

    def pytest_collect_file(self, file_path: Path, parent: pytest.Collector) -> Optional[pytest.Collector]:
        """Make pytest.Collectors for Jupyter Notebooks."""
        if file_path.suffix in [".ipynb"]:
            func_manager = parent.config.stash[self.__FUNCTION_HANDLER_KEY]
            func_manager.add_scoped_hook_for_file(parent.config.pluginmanager, file_path)
            return cast(
                JupyterNotebookFile,
                JupyterNotebookFile.from_parent(
                    parent,
                    path=file_path,
                    test_functions=func_manager.test_functions_for(file_path),
                ),
            )
        return None

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
