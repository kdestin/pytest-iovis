import errno
import os
from pathlib import Path
from typing import Callable, List, NoReturn, Union

import pytest

from .._utils import error_message_at_mark_owner, make_mark_description


def notebook(path: Union[os.PathLike, str]) -> Path:
    """Associate a test function with a Jupyter Notebook.

    This function is only used to generate documentation for the `notebook` marker (docstring + signature)
    """
    return path


class NotebookMarkerHandler:
    """A pytest plugin that manages the semantics of the `@pytest.mark.notebook` mark."""

    MARKER_NAME = notebook.__name__
    """The name of the marker managed by this plugin"""

    def pytest_configure(self, config: pytest.Config) -> None:
        """Register the marker handled by this plugin"""

        config.addinivalue_line("markers", make_mark_description(notebook))

    @staticmethod
    def normalize_marker_args(
        item: pytest.Item,
        mark: pytest.Mark,
        *,
        on_error: Callable[[Union[str, Exception], pytest.Item, pytest.Mark], NoReturn],
    ) -> Path:
        """Normalize and return the arguments of the pytest marker. If args are invalid and can't be normalized,
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
        try:
            # Validate the marker parameters
            path = notebook(*mark.args, **mark.kwargs)
        except TypeError as e:
            on_error(e, item, mark)

        abs_path = Path(path) if Path(path).is_absolute() else Path(item.path.parent, path).resolve()

        if not abs_path.exists():
            on_error(FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(abs_path)), item, mark)

        if not abs_path.is_file():
            on_error(f"Not a file '{abs_path}'", item, mark)

        return abs_path

    def pytest_collection_modifyitems(self, items: List[pytest.Item]) -> None:
        def on_validation_error(e: Union[str, Exception], item: pytest.Item, mark: pytest.Mark) -> NoReturn:
            raise pytest.UsageError(error_message_at_mark_owner(e, item, mark))

        for i in items:
            for m in i.iter_markers(name=self.MARKER_NAME):
                self.normalize_marker_args(i, m, on_error=on_validation_error)
