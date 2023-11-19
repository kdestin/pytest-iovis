import types
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple, Union, cast

import pytest
from typing_extensions import TypeGuard

from .._file import JupyterNotebookFile
from .._types import PathType, SetTestsForFileCallback, SetTestsHook, TestObject
from .._utils import PathTrie, partition


class SetFunctionHookSpec:
    @pytest.hookspec(firstresult=True)
    def pytest_iovis_set_tests(
        self,
        current_tests: Tuple[TestObject, ...],
        tests_for: Callable[[PathType], Callable[[SetTestsForFileCallback], None]],
    ) -> Optional[Iterable[TestObject]]:
        """Set the default test functions for collected Jupyter Notebooks.

        The defaults returned by this hook apply to all collected notebooks under the parent directory this is
        called from.

        This hook will only be called when found in `conftest.py`.

        :param current_tests: The test functions that currently apply to the given scope.
        :type current_tests: Tuple[TestObject, ...]
        :return: Either:
            * A iterable of test functions that will be used for all collected notebooks
            * None, which is equivalent to this hook not having been called
        :rtype: Optional[Iterable[TestObject]]
        """
        raise NotImplementedError()


# Useless assignment so that mypy ensures the hook implements protocol
_: SetTestsHook = SetFunctionHookSpec().pytest_iovis_set_tests


class ScopedFunctionHandler:
    """A plugin that builds an index that can be used to query which test function to use for a given path.

    .. note::

        This plugin relies on some _technically_ undocumented behavior of pytest.

        `pytest` discovers `conftest.py`'s as it performs collection, registering new ones it finds _as soon_ as it
        descends into a new directory. This ordering is perfect for us, since it means that we can do an online build
        of our index as pytest discovers `conftest.py`'s. And we know that once its time to collect a file that we
        care about, all the relevant conftest.py's are in our index.

    """

    HOOK_NAME = SetFunctionHookSpec.pytest_iovis_set_tests.__name__

    def __init__(self) -> None:
        # Assigning to the instance instead of stashing in a session because the session object isn't available in
        # pytest_plugin_registered.
        self.file_hooks: Dict[Path, SetTestsHook] = {}
        self.path_trie: Optional[PathTrie[Tuple[TestObject, ...]]] = None

    def _initialize_trie(self, manager: pytest.PytestPluginManager) -> None:
        """Initialize our path_trie with the global test functions and any already collected conftest.py."""
        all_plugins = manager.get_plugins()
        conftest_plugins, non_conftest_plugins = partition(all_plugins, self.is_conftest)

        non_conftest_hooks = self.call_hook_without(manager, conftest_plugins)
        result = non_conftest_hooks(current_tests=(), tests_for=lambda _: lambda _: None)

        global_test_functions = tuple(result or ())

        self.path_trie = PathTrie(root_payload=global_test_functions)
        for conftest in sorted(conftest_plugins, key=lambda c: Path(c.__file__ or "")):
            assert conftest.__file__
            self.add_scoped_hook(
                manager,
                Path(conftest.__file__).parent,
                self.call_hook_without(manager, all_plugins.difference({conftest})),
            )

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collect_file(self, parent: pytest.Collector) -> Iterable[None]:
        if self.path_trie is None:
            self._initialize_trie(parent.config.pluginmanager)

        yield

    def pytest_addhooks(self, pluginmanager: pytest.PytestPluginManager) -> None:
        """Register the `pytest_iovis_set_tests` hook."""
        pluginmanager.add_hookspecs(SetFunctionHookSpec)

    @staticmethod
    def is_conftest(obj: object) -> TypeGuard[types.ModuleType]:
        return isinstance(obj, types.ModuleType) and Path(obj.__file__ or ".").name == "conftest.py"

    @staticmethod
    def call_hook_without(manager: pytest.PytestPluginManager, plugins: Iterable[object]) -> SetTestsHook:
        """Return the hook function that runs on all plugins except the supplied ones."""
        return manager.subset_hook_caller(ScopedFunctionHandler.HOOK_NAME, remove_plugins=plugins)

    def pytest_plugin_registered(self, plugin: object, manager: pytest.PytestPluginManager) -> None:
        if not self.is_conftest(plugin):
            return

        assert plugin.__file__

        self.add_scoped_hook(
            manager,
            Path(plugin.__file__).parent,
            self.call_hook_without(manager, manager.get_plugins().difference({plugin})),
        )

    def add_scoped_hook(self, manager: pytest.PytestPluginManager, scope: Path, hook: SetTestsHook) -> None:
        """Invoke the hook function for the specified scope, and add the result to our function index.

        :param pytest.PytestPluginManager manager: The pytest plugin manager for the current session
        :param Path scope: The scope the hook applies to
        :param SetTestFunctionHook hook: The hook function to invoke
        """
        path_trie = self.path_trie
        if path_trie is None:
            return

        if scope in path_trie:
            return

        empty_hook_caller = manager.subset_hook_caller(self.HOOK_NAME, manager.get_plugins())

        def make_register_fn(
            confdir: Path,
        ) -> Callable[[PathType], Callable[[SetTestsForFileCallback], None]]:
            def tests_for(path: PathType) -> Callable[[SetTestsForFileCallback], None]:
                pathlib_path = Path(path) if Path(path).is_absolute() else Path(scope, path).resolve()
                __tracebackhide__ = True  # Hide this function from traceback
                if confdir not in pathlib_path.parents:
                    pytest.fail(f"{tests_for.__name__}'s path must be a subpath of the calling conftest's directory.")

                if not pathlib_path.is_file():
                    pytest.fail(f"Not a file: {pathlib_path}")

                def decorator(f: SetTestsForFileCallback) -> None:
                    def hook(
                        current_tests: Tuple[TestObject, ...], tests_for: object  # noqa: ARG001
                    ) -> Iterable[TestObject]:
                        return cast(
                            Iterable[TestObject],
                            empty_hook_caller.call_extra(
                                [f], {"current_tests": current_tests, "tests_for": make_register_fn(pathlib_path)}
                            ),
                        )

                    self.file_hooks[pathlib_path] = hook

                return decorator

            return tests_for

        current_funcs = self.test_functions_for(scope)
        functions_for_scope = hook(current_tests=tuple(current_funcs), tests_for=make_register_fn(scope))
        if functions_for_scope is None:
            return

        # Sanity check to make sure we're getting scopes that are always more specific
        assert path_trie.insert(scope, tuple(functions_for_scope)) == PathTrie.InsertType.LEAF

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

    def test_functions_for(self, p: PathType) -> Iterable[TestObject]:
        """Compute the test functions that are in-scope at a given path.

        This function should be called within TestFunctionManager.with_populated_trie.


        :param pytest.Session session: The pytest session
        :param PathType p: The path to find tests for.
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

    @pytest.hookimpl(trylast=True)
    def pytest_iovis_set_tests(self) -> Iterable[TestObject]:
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
        if not cls.is_managed_function(item):
            return None

        try:
            return item.path
        except ValueError:
            return None
