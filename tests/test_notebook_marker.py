import os
from pathlib import Path
from typing import Callable, Optional, Union

import pytest


@pytest.fixture()
def testdir(testdir: pytest.Testdir, monkeypatch: pytest.MonkeyPatch) -> pytest.Testdir:
    """Return the testdir fixutre, but ensure that the grouping subplugin is disabled and doesn't affect output."""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p no:papermill.grouping")
    return testdir


def test_notebook_marker_documentation(testdir: pytest.Testdir) -> None:
    """Check that `pytest --markers` displays a help message for @pytest.mark.notebook."""
    res = testdir.runpytest("--markers")

    res.stdout.fnmatch_lines(
        "@pytest.mark.notebook(path: Union[[]os.PathLike, str]): Associate a test function with a Jupyter Notebook."
    )

    assert res.ret == 0


class TestErrorMessages:
    def test_file_doesnt_exist(self, testdir: pytest.Testdir) -> None:
        """Verify that a reasonable error message is shown when the path doesn't exist."""
        nonexistant_path = Path("path", "does", "not", "exist.ipynb")

        testdir.makepyfile(
            f"""
            import pytest

            @pytest.mark.notebook({str(nonexistant_path)!r})
            def test_marker():
                pass
        """
        )

        res = testdir.runpytest_subprocess("--collect-only")

        res.assert_outcomes(errors=1)
        res.stdout.fnmatch_lines(f"*.py::test_marker: [[]Errno 2] No such file or directory: '*{nonexistant_path}'")

        assert res.ret != 0

    def test_not_a_file(self, testdir: pytest.Testdir) -> None:
        """Verify that a reasonable error message is shown when path does exist but isn't a file."""
        not_a_file = "not_a_file.ipynb"

        testdir.mkdir(not_a_file)
        testdir.makepyfile(
            f"""
            import pytest

            @pytest.mark.notebook({not_a_file!r})
            def test_marker():
                pass
        """
        )

        res = testdir.runpytest_subprocess("--collect-only")

        res.assert_outcomes(errors=1)
        res.stdout.fnmatch_lines(f"*.py::test_marker: Not a file '*/{not_a_file}'")

        assert res.ret != 0

    @pytest.mark.parametrize(
        "marker", ["not_a_keyword_param=None", "'path1.ipynb', 'path2.ipynb'"], ids=lambda args: f"notebook({args})"
    )
    def test_incorrect_function_call(self, testdir: pytest.Testdir, marker: str) -> None:
        """Verify that we show an error message if notebook marker is invoked incorrectly."""
        testdir.makepyfile(
            f"""
            import pytest

            @pytest.mark.notebook({marker})
            def test_marker():
                pass
        """
        )

        res = testdir.runpytest_subprocess("--collect-only")

        res.assert_outcomes(errors=1)

        # We're leveraging python's error messages when functions are called incorrectly, so we're not fully asserting
        # the error message
        res.stdout.fnmatch_lines("*.py::test_marker: notebook() *")

        assert res.ret != 0


def test_no_marker_applied(testdir: pytest.Testdir) -> None:
    """Ensure that we do not parametrize a test function that has no marker applied."""
    testfile_path = Path("tests", "test.py")

    testdir.makepyfile(
        **{
            f"{testfile_path}": """
        def test_marker(notebook_path):
            pass
    """,
        },
    )

    res = testdir.runpytest("--collect-only", str(testfile_path))
    outcomes = res.parseoutcomes()
    num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

    assert num_collected_tests == 1
    res.stdout.fnmatch_lines(["<Module tests/test.py>", "  <Function test_marker>", ""])


def test_single_marker_applied(testdir: pytest.Testdir) -> None:
    """Check that applying a notebook mark multiple times creates a parametrized function for each mark."""
    notebook_path = Path(testdir.test_tmproot, "notebooks", "test.ipynb").resolve()
    testfile_path = Path("tests", "test.py")

    testdir.makefile(".ipynb", **{str(notebook_path): ""})
    testdir.makepyfile(
        **{
            f"{testfile_path}": f"""
        import pytest

        @pytest.mark.notebook({str(notebook_path)!r})
        def test_marker(notebook_path):
            pass
    """,
        },
    )

    res = testdir.runpytest("--collect-only", str(testfile_path))
    outcomes = res.parseoutcomes()
    num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

    assert num_collected_tests == 1
    res.stdout.fnmatch_lines(
        ["<Module tests/test.py>", f"  <JupyterNotebookTestFunction test_marker[[]{notebook_path}]>", ""]
    )


def test_multiple_unique_markers_applied(testdir: pytest.Testdir) -> None:
    """Check that applying a notebook mark multiple times creates a parametrized function for each mark."""
    notebook_paths = [Path("notebooks", f"test{i}.ipynb").resolve() for i in range(3)]
    testfile_path = Path("tests", "test.py")

    testdir.makefile(".ipynb", **{str(p): "" for p in notebook_paths})
    testdir.makepyfile(
        **{
            f"{testfile_path}": f"""
        import pytest

        @pytest.mark.notebook({str(notebook_paths[0])!r})
        @pytest.mark.notebook({str(notebook_paths[1])!r})
        @pytest.mark.notebook({str(notebook_paths[2])!r})
        def test_marker(notebook_path):
            pass
    """,
        },
    )

    res = testdir.runpytest("--collect-only", str(testfile_path))
    outcomes = res.parseoutcomes()
    num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

    assert num_collected_tests == 3
    res.stdout.fnmatch_lines(
        [
            "<Module tests/test.py>",
            f"  <JupyterNotebookTestFunction test_marker[[]{notebook_paths[0]}]>",
            f"  <JupyterNotebookTestFunction test_marker[[]{notebook_paths[1]}]>",
            f"  <JupyterNotebookTestFunction test_marker[[]{notebook_paths[2]}]>",
            "",
        ]
    )


def test_duplicated_markers_applied(testdir: pytest.Testdir) -> None:
    """Check that markers that refer to the same path are deduplicated."""
    notebook_paths = [Path("notebooks", f"test{i}.ipynb").resolve() for i in range(3)]
    testfile_path = Path("tests", "test.py")

    testdir.makefile(".ipynb", **{str(p): "" for p in notebook_paths})
    testdir.makepyfile(
        **{
            f"{testfile_path}": f"""
        from pathlib import Path

        import pytest

        @pytest.mark.notebook({str(notebook_paths[0])!r})
        @pytest.mark.notebook({str(Path(testdir.tmpdir, notebook_paths[0]))!r})
        @pytest.mark.notebook({str(Path("notebooks", "..", notebook_paths[0]))!r})
        @pytest.mark.notebook({str(notebook_paths[1])!r})
        @pytest.mark.notebook({str(notebook_paths[2])!r})
        @pytest.mark.notebook({str(notebook_paths[0])!r})
        @pytest.mark.notebook(Path({str(notebook_paths[0])!r}))
        def test_marker(notebook_path):
            pass
    """,
        },
    )

    res = testdir.runpytest("--collect-only", str(testfile_path))
    outcomes = res.parseoutcomes()
    num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

    assert num_collected_tests == 3
    res.stdout.fnmatch_lines(
        [
            "<Module tests/test.py>",
            f"  <JupyterNotebookTestFunction test_marker[[]{notebook_paths[0]}]>",
            f"  <JupyterNotebookTestFunction test_marker[[]{notebook_paths[1]}]>",
            f"  <JupyterNotebookTestFunction test_marker[[]{notebook_paths[2]}]>",
            "",
        ]
    )


class TestDefaultFunctionsRemoved:
    """Tests that check that automatically generated tests for notebooks are removed when a user-defined one exists."""

    def test_with_default_test_function(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Check that a user defined test function for notebook removes the automatically generated test functions."""
        testfile_path = Path("tests", "test.py")

        testdir.makepyfile(
            **{
                f"{testfile_path}": f"""
            from pathlib import Path

            import pytest

            @pytest.mark.notebook({str(dummy_notebook)!r})
            def test_marker(notebook_path):
                pass
        """,
            },
        )

        res = testdir.runpytest("--collect-only", str(testfile_path), str(dummy_notebook), "-v")

        outcomes = res.parseoutcomes()
        num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

        assert num_collected_tests == 1

        res.stdout.fnmatch_lines(
            [
                "<Module tests/test.py>",
                f"  <JupyterNotebookTestFunction test_marker[[]{dummy_notebook}]>",
                "",
            ],
            consecutive=True,
        )

    def test_does_not_affect_non_overriden_functions(
        self,
        dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path],
        testdir: pytest.Testdir,
    ) -> None:
        """Check that non overriden functions are unaffected."""
        notebook_paths = [str(dummy_notebook_factory(Path("notebooks", f"test{i}.ipynb"))) for i in range(3)]
        testfile_path = Path("tests", "test.py")

        testdir.makepyfile(
            **{
                f"{testfile_path}": f"""
            from pathlib import Path

            import pytest

            @pytest.mark.notebook({notebook_paths[0]!r})
            def test_marker(notebook_path):
                pass
        """,
            },
        )

        res = testdir.runpytest("--collect-only", str(testfile_path), *notebook_paths, "-v")

        outcomes = res.parseoutcomes()
        num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

        assert num_collected_tests == 3

        res.stdout.fnmatch_lines(
            [
                "<Module tests/test.py>",
                f"  <JupyterNotebookTestFunction test_marker[[]{notebook_paths[0]}]>",
                "<JupyterNotebookFile notebooks/test1.ipynb>",
                f"  <JupyterNotebookTestFunction test_notebook_runs[[]{notebook_paths[1]}]>",
                "<JupyterNotebookFile notebooks/test2.ipynb>",
                f"  <JupyterNotebookTestFunction test_notebook_runs[[]{notebook_paths[2]}]>",
                "",
            ],
            consecutive=True,
        )

    def test_with_user_test_functions(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Check that a user defined test function for notebook removes the automatically generated test functions."""
        testfile_path = Path("tests", "test.py")

        testdir.makeconftest(
            """
            from pytest_papermill import register_default_test_functions

            def test_notebook_1(notebook_path):
                pass

            def test_notebook_2(notebook_path):
                pass

            def pytest_configure(config):
                register_default_test_functions(test_notebook_1, test_notebook_2, config=config)
            """
        )

        testdir.makepyfile(
            **{
                f"{testfile_path}": f"""
            from pathlib import Path

            import pytest

            @pytest.mark.notebook({str(dummy_notebook)!r})
            def test_marker(notebook_path):
                pass
        """,
            },
        )

        res = testdir.runpytest("--collect-only", str(testfile_path), str(dummy_notebook), "-v")

        outcomes = res.parseoutcomes()
        num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

        assert num_collected_tests == 1

        res.stdout.fnmatch_lines(
            [
                "<Module tests/test.py>",
                f"  <JupyterNotebookTestFunction test_marker[[]{dummy_notebook}]>",
                "",
            ],
            consecutive=True,
        )
