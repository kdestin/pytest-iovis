import errno
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, NoReturn, Optional, Union, cast

import pytest
from typing_extensions import TypeGuard

from .._file import JupyterNotebookTestFunction
from .._utils import error_message_at_mark_owner, make_mark_description


@dataclass
class NotebookMarkerArg:
    original_path: Union[os.PathLike, str]
    """The untouched argument provided by the user in the notebook marker"""

    def resolved_path(self, item: pytest.Item) -> Path:
        """Resolve the path argument relative to the location of the pytest Item.

        :param pytest.Item item: The pytest item to resolve the path relative to
        :return: Either
            * The original path if it is absolute
            * An absolute path formed by resolving `path` relative to the path of the pytest item
        :rtype: Path
        """
        return (
            Path(self.original_path)
            if Path(self.original_path).is_absolute()
            else Path(item.path.parent, self.original_path).resolve()
        )


def notebook(path: Union[os.PathLike, str]) -> NotebookMarkerArg:
    """Associate a test function with a Jupyter Notebook.

    This function is only used to generate documentation for the `notebook` marker (docstring + signature)
    """
    return NotebookMarkerArg(original_path=path)


class NotebookMarkerHandler:
    """A pytest plugin that manages the semantics of the `@pytest.mark.notebook` mark."""

    MARKER_NAME = notebook.__name__
    """The name of the marker managed by this plugin"""

    FIXTURE_NAME = "notebook_path"
    """The name of the fixture that will be parametrized by this plugin"""

    def pytest_configure(self, config: pytest.Config) -> None:
        """Register the marker handled by this plugin"""

        config.addinivalue_line("markers", make_mark_description(notebook))

    @staticmethod
    def validate_marker_args(
        item: pytest.Item,
        mark: pytest.Mark,
        *,
        on_error: Callable[[Union[str, Exception], pytest.Item, pytest.Mark], NoReturn],
    ) -> NotebookMarkerArg:
        """Validate and return the arguments of the pytest marker. If args are invalid and can't be normalized,
        call on_error

        :param pytest.Item item: The pytest item the mark was found on
        :param pytest.Mark mark: A pytest mark
        :keyword on_error: A callable that *doesn't return* to call when normalization fails.
            .. note::

                Error handling in pytest plugins is kinda weird. The pytest documentation states that you can't
                throw exceptions:

                    Note that hook functions other than pytest_runtest_* are not allowed to raise exceptions. Doing so
                    will break the pytest run.

                Conventially throwing exceptions will produce a large block of text prefixed by "INTERNALERROR>", which
                is hard for users to parse.

                pytest does have some special handling for some specific exceptions in some contexts:

                * ``pytest.UsageError`` can produce a very concise error message when thrown.
                  See https://github.com/pytest-dev/pytest/discussions/10211#discussioncomment-3387635
                * Some internal pytest code uses `pytest.fail(message, pytrace=False)` to signal an error

                Their handling seems to depend on the hook it's called from, and can either be a nicely formatted
                message, or an internal error.
        :type on_error: Callable[[Union[str, Exception], pytest.Item, pytest.Mark], NoReturn]
        """
        exception = None
        try:
            # Validate the marker parameters
            args = notebook(*mark.args, **mark.kwargs)
        except TypeError as e:
            # Save the exception so on_error is called outside the context of an ongoing exception
            exception = e

        if exception is not None:
            on_error(exception, item, mark)

        abs_path = args.resolved_path(item)

        if not abs_path.exists():
            on_error(FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(abs_path)), item, mark)

        if not abs_path.is_file():
            on_error(f"Not a file '{abs_path}'", item, mark)

        return args

    @classmethod
    def is_marked_function(cls, item: Union[pytest.Item, pytest.Collector]) -> TypeGuard[pytest.Function]:
        """Check whether the pytest.Item is a pytest.Function with the notebook marker applied."""
        return isinstance(item, pytest.Function) and next(item.iter_markers(name=cls.MARKER_NAME), None) is not None

    @classmethod
    def get_notebook_path(cls, item: Union[pytest.Item, pytest.Collector]) -> Optional[Path]:
        """Get the notebook path associated with a test function."""
        isParameterizedFunction = isinstance(item, pytest.Function) and hasattr(item, "callspec")

        if not isParameterizedFunction:
            return None

        if not cls.is_marked_function(item):
            return None

        try:
            args = cast(NotebookMarkerArg, item.callspec.getparam(cls.FIXTURE_NAME))
            return args.resolved_path(item)
        except ValueError:
            return None

    def pytest_make_parametrize_id(self, val: object, argname: str) -> Optional[str]:
        """Use the strigified argument the user provided as the parametrization ID."""
        if not (isinstance(val, NotebookMarkerArg) and argname == NotebookMarkerHandler.FIXTURE_NAME):
            return None

        return f"{(cast(NotebookMarkerArg, val).original_path)}"

    def pytest_generate_tests(self, metafunc: pytest.Metafunc) -> None:
        """Generate a test function for each applied @pytest.mark.notebook mark by parametrizing the `notebook_path`
        argument.
        """

        def on_validation_error(e: Union[str, Exception], item: pytest.Item, mark: pytest.Mark) -> NoReturn:
            pytest.fail(error_message_at_mark_owner(e, item, mark), pytrace=False)

        def deduplicate(args: Iterable[NotebookMarkerArg]) -> Iterable[NotebookMarkerArg]:
            """Remove NotebookMarkerArgs whose resolved path as already been seen"""
            d: Dict[Path, NotebookMarkerArg] = {}
            for a in args:
                d.setdefault(a.resolved_path(metafunc.definition), a)
            return d.values()

        markers = list(metafunc.definition.iter_markers(name=self.MARKER_NAME))

        if not markers:
            return

        # Markers are returned from closest to furthers from the function definition. Reversing the order makes
        # the collection report more closely match the source.
        markers.reverse()

        args = deduplicate(
            self.validate_marker_args(metafunc.definition, m, on_error=on_validation_error) for m in markers
        )

        # Indirect Parameterization allow's for the user's input to be used as the test ID, and delay resolving it
        # to a user's input to a pathlib.Path until right before the fixture actually produces a value.
        metafunc.parametrize(self.FIXTURE_NAME, args, indirect=True)

    def pytest_collection_modifyitems(self, items: List[pytest.Item]) -> None:
        """Replace `@pytest.mark.notebook` marked `pytest.Function`s with JupyterNoteTestFunction."""

        # marked pytest.Function -> JupyterNotebookTestFunction
        for i, item in enumerate(items):
            if self.is_marked_function(item):
                items[i] = JupyterNotebookTestFunction.from_function(item.parent, item)
