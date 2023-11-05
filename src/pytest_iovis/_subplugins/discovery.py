import types
from pathlib import Path
from typing import (
    Callable,
    Generator,
    Generic,
    Iterable,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

import pluggy
import pytest
from typing_extensions import TypeAlias, TypeGuard

from .._file import JupyterNotebookFile
from .._utils import partition
from .notebook_marker import NotebookMarkerHandler

T_OpaqueCallable: TypeAlias = Callable[..., object]
"""A type alias for a callable with opaque types (vs Any)."""
T_File = TypeVar("T_File", bound=pytest.File)
T = TypeVar("T")

TestObject = Union[Type[object], T_OpaqueCallable]


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


class SetDefaultHookFunction(Protocol):
    def __call__(self) -> Optional[Iterable[TestObject]]:
        raise NotImplementedError()


class TestFunctionManager:
    __DEFAULT_FUNCTIONS = pytest.StashKey[Tuple[TestObject, ...]]()

    def pytest_addhooks(self, pluginmanager: pytest.PytestPluginManager) -> None:
        class HookSpec:
            @pytest.hookspec(firstresult=True)
            def pytest_iovis_set_default_functions(self) -> Optional[Iterable[TestObject]]:
                """Set the default test functions for collected Jupyter Notebooks.

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

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection(self, session: pytest.Session) -> Iterable[None]:
        def call_hook_without(plugins: Iterable[object]) -> SetDefaultHookFunction:
            """Return the hook function that runs on all plugins except the supplied ones."""
            return manager.subset_hook_caller("pytest_iovis_set_default_functions", remove_plugins=plugins)

        manager = session.config.pluginmanager

        all_plugins = manager.get_plugins()
        conftest_plugins, non_conftest_plugins = partition(all_plugins, self.is_conftest)

        non_conftest_hooks = call_hook_without(conftest_plugins)
        conftest_hooks = call_hook_without(non_conftest_plugins)

        session.stash[self.__DEFAULT_FUNCTIONS] = tuple(
            next((fs for fs in (conftest_hooks(), non_conftest_hooks()) if fs is not None), [])
        )
        yield

        del session.stash[self.__DEFAULT_FUNCTIONS]

    def test_functions_for(self, session: pytest.Session) -> Tuple[TestObject, ...]:
        return session.stash.get(self.__DEFAULT_FUNCTIONS, ())


class JupyterNotebookDiscoverer:
    """A pytest plugin that enables auto-discovery of Jupyter notebooks as pytest tests.

    .. note::

        Jupyter Notebooks are *conditionally* collected based on whether a user-defined test function marked
        with @pytest.mark.notebook that points to that notebook is also collected in the same test session.

        That is, notebook "path/to/notebook.ipynb" will *not* be collected by this plugin if a test like the following
        has been collected:

            @pytest.mark.notebook("path/to/notebook.ipynb")
            def test_function(notebook_path):
                ...

        Implementers Note: This is achieved by delaying the collection of JupyterNotebookFile until all other
            pytest.File collectors have been collected.
    """

    PLUGIN_NAME = "notebook_discovery"
    """A user facing name that describes this plugin."""
    __USER_DEFINED_PATHS_KEY = pytest.StashKey[Set[Path]]()
    """A stash key that stores notebook Paths with user-defined test functions. Meant to be used on a session."""
    __DELAYER_NAME = "jupyter_notebook_file_delayer"
    __FUNCTION_MANAGER_KEY = pytest.StashKey[TestFunctionManager]()

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
            function_manager = parent.session.config.stash[self.__FUNCTION_MANAGER_KEY]
            return cast(
                JupyterNotebookFile,
                JupyterNotebookFile.from_parent(
                    parent, path=file_path, test_functions=function_manager.test_functions_for(parent.session)
                ),
            )
        return None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection(self, session: pytest.Session) -> Iterable[None]:
        """Initialize session variables."""
        session.stash[self.__USER_DEFINED_PATHS_KEY] = cast(Set[Path], set())

        yield

        del session.stash[self.__USER_DEFINED_PATHS_KEY]

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

        if not delayer.is_pytest_collecting(session):
            return

        seen_user_paths = session.stash[self.__USER_DEFINED_PATHS_KEY]
        seen_user_paths.update(p for p in map(NotebookMarkerHandler.get_notebook_path, report.result) if p is not None)

        if delayer.is_last_make_collect_report_for_file(session):
            delayed_collectors = delayer.get_delayed(session)
            # Remove collectors for notebooks that already have a user-defined test function
            delayed_collectors[:] = [i for i in delayed_collectors if i.path.resolve() not in seen_user_paths]
            # Queue the collectors for collection
            delayer.add_delayed(report, delayed_collectors)
