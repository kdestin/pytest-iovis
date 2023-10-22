import os
from pathlib import Path
from typing import Callable, Optional, Union

import pytest


def test_no_mark_on_test_function(testdir: pytest.Testdir) -> None:
    """Verify that collection isn't affected if the notebook marker is not present."""
    testdir.makepyfile(
        """
        def test_function():
            pass

        def test_function2():
            pass
    """
    )

    res = testdir.runpytest("--collect-only")

    res.stdout.fnmatch_lines(
        [
            "",
            "<Module test_no_mark_on_test_function.py>",
            "  <Function test_function>",
            "  <Function test_function2>",
            "",
        ],
        consecutive=True,
    )


def test_single_mark_on_test_function(
    dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path], testdir: pytest.Testdir
) -> None:
    """Verify that applying a single marker parents the test function to a JupyterNotebookFile."""
    notebook_paths = [str(dummy_notebook_factory(f"test{i}.ipynb")) for i in range(2)]
    testfile = testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.notebook({notebook_paths[0]!r})
        def test_function(self, notebook_path):
            pass

        @pytest.mark.notebook({notebook_paths[1]!r})
        def test_function2(self, notebook_path):
            pass
    """
    )

    res = testdir.runpytest("--collect-only", testfile)

    res.stdout.fnmatch_lines(
        [
            "",
            "<JupyterNotebookFile test0.ipynb>",
            "  <JupyterNotebookTestFunction test_function>",
            "<JupyterNotebookFile test1.ipynb>",
            "  <JupyterNotebookTestFunction test_function2>",
            "",
        ],
        consecutive=True,
    )


def test_multiple_marks_on_test_function(
    dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path], testdir: pytest.Testdir
) -> None:
    """Verify that applying n markers makes n copies of the test function for each notebook path."""
    notebook_paths = [str(dummy_notebook_factory(f"test{i}.ipynb")) for i in range(3)]
    testfile = testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.notebook({notebook_paths[0]!r})
        @pytest.mark.notebook({notebook_paths[1]!r})
        @pytest.mark.notebook({notebook_paths[2]!r})
        def test_function(self, notebook_path):
            pass

    """
    )

    res = testdir.runpytest("--collect-only", testfile)

    res.stdout.fnmatch_lines(
        [
            "",
            "<JupyterNotebookFile test0.ipynb>",
            "  <JupyterNotebookTestFunction test_function>",
            "<JupyterNotebookFile test1.ipynb>",
            "  <JupyterNotebookTestFunction test_function>",
            "<JupyterNotebookFile test2.ipynb>",
            "  <JupyterNotebookTestFunction test_function>",
            "",
        ],
        consecutive=True,
    )


def test_class_object_fan_out(
    dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path], testdir: pytest.Testdir
) -> None:
    """Verify that class lineage is preserved, and classes are duplicate as needed."""
    notebook_paths = [str(dummy_notebook_factory(f"test{i}.ipynb")) for i in range(3)]
    testfile = testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.notebook({notebook_paths[0]!r})
        @pytest.mark.notebook({notebook_paths[1]!r})
        class TestClass:
            @pytest.mark.notebook({notebook_paths[2]!r})
            def test_function(self, notebook_path):
                pass

            def test_function2(self, notebook_path):
                pass
    """
    )

    res = testdir.runpytest("--collect-only", testfile)

    res.stdout.fnmatch_lines(
        [
            "",
            "<JupyterNotebookFile test0.ipynb>",
            "  <Class TestClass>",
            "    <JupyterNotebookTestFunction test_function>",
            "    <JupyterNotebookTestFunction test_function2>",
            "<JupyterNotebookFile test1.ipynb>",
            "  <Class TestClass>",
            "    <JupyterNotebookTestFunction test_function>",
            "    <JupyterNotebookTestFunction test_function2>",
            "<JupyterNotebookFile test2.ipynb>",
            "  <Class TestClass>",
            "    <JupyterNotebookTestFunction test_function>",
            "",
        ],
        consecutive=True,
    )
