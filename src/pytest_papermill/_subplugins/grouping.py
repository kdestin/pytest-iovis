import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pytest

from .._file import JupyterNotebookFile, JupyterNotebookTestFunction
from .._utils import partition
from .notebook_marker import NotebookMarkerArg, NotebookMarkerHandler


class NotebookGrouper:
    PLUGIN_NAME = "grouping"
    """A user facing name that describes this plugin."""

    __PLACEHOLDER_NOTEBOOK_PARAMSET_ID = f"{uuid.uuid4()}{uuid.uuid4()}"

    def pytest_make_parametrize_id(self, argname: str, val: object) -> Optional[str]:
        """Return a placeholder ID when parametrizing on the notebook path fixture that can be later removed."""
        if not (isinstance(val, NotebookMarkerArg) and argname == NotebookMarkerHandler.FIXTURE_NAME):
            return None

        return self.__PLACEHOLDER_NOTEBOOK_PARAMSET_ID

    @pytest.hookimpl(trylast=True)
    def pytest_generate_tests(self, metafunc: pytest.Metafunc) -> None:
        """Remove the placeholder notebook name from the callspec ID list."""
        markers = list(metafunc.definition.iter_markers(name=NotebookMarkerHandler.MARKER_NAME))

        if not markers:
            return

        for c in metafunc._calls:
            c._idlist[:] = [s for s in c._idlist if not s.startswith(self.__PLACEHOLDER_NOTEBOOK_PARAMSET_ID)]

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session: pytest.Session, items: List[pytest.Item]) -> None:
        """Group @pytest.mark.notebook marked test_functions by notebook path.

        That is, we're turning this:

            <Module tests/test_test.py>
              <JupyterNotebookTestFunction test_notebook[tests/notebook/foo.ipynb]>
              <Class TestClassGood>
                <JupyterNotebookTestFunction test_notebook[tests/notebook/foo.ipynb]>
                <JupyterNotebookTestFunction test_notebook2[tests/notebook/bar.ipynb]>
                <JupyterNotebookTestFunction test_notebook[tests/notebook/foo.ipynb]>
                <JupyterNotebookTestFunction test_notebook2[tests/notebook/bar.ipynb]>
              <Class TestClassBad>
                <Function test_notebook>
                <Function test_notebook2>

        into this:

            <JupyterNotebookFile tests/notebooks/foo.ipynb>
              <JupyterNotebookTestFunction test_notebook[tests/notebook/foo.ipynb]>
              <Class TestClassGood>
                <JupyterNotebookTestFunction test_notebook[tests/notebook/foo.ipynb]>
                <JupyterNotebookTestFunction test_notebook2[tests/notebook/foo.ipynb]>
            <JupyterNotebookFile tests/notebooks/bar.ipynb>
              <Class TestClassGood>
                <JupyterNotebookTestFunction test_notebook[tests/notebook/bar.ipynb]>
                <JupyterNotebookTestFunction test_notebook2[tests/notebook/bar.ipynb]>
            <Module tests/test_test.py>
              <Class TestClassBad>
                <Function test_notebook>
                <Function test_notebook2>

        """

        def make_reparent(session: pytest.Session) -> Callable[[pytest.Function], Optional[pytest.Collector]]:
            notebook_paths: Dict[Path, Dict[Optional[pytest.Class], pytest.Collector]] = {}
            """Absolute Path -> None (for root file collector), pytest.Class -> new Parent."""

            def reparent(item: pytest.Item) -> Optional[pytest.Collector]:
                path: Optional[Path] = NotebookMarkerHandler.get_notebook_path(item)

                if path is None:
                    return None

                parents = notebook_paths.setdefault(path, {})
                file_root = parents.setdefault(
                    None, JupyterNotebookFile.from_parent(session, path=path, test_functions=[])
                )

                if isinstance(item.parent, pytest.File):
                    return file_root
                if isinstance(item.parent, pytest.Class):
                    return parents.setdefault(
                        item.parent,
                        pytest.Class.from_parent(  # type: ignore[no-untyped-call]
                            file_root, name=item.parent.name, obj=item.parent.obj
                        ),
                    )

                return None

            return reparent

        notebook_functions, items[:] = partition(items, NotebookMarkerHandler.is_marked_function)
        reparent = make_reparent(session)

        for i, item in enumerate(notebook_functions):
            # Remove empty parameterization brackets
            if item.name.endswith("[]"):
                item.name = item.name[:-2]

            newParent = reparent(item)

            # This is _should_ never happen
            if newParent is None:
                raise ValueError(f"Unable to determine new parent for {item!r}")

            notebook_functions[i] = JupyterNotebookTestFunction.from_function(reparent(item), item)

        # Pytest seems to rely on some implicit ordering to correctly group together tests in the test report
        # Sorting by parent nodeid allows us to preserve parameterization ordering
        notebook_functions.sort(key=lambda i: i.parent.nodeid if i.parent is not None else "")

        items.extend(notebook_functions)
