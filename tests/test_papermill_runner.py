import json
from pathlib import Path
from typing import Callable, Optional

import pytest

from pytest_iovis import PathType


class TestFixtures:
    def test_documentation(self, testdir: pytest.Testdir) -> None:
        """Validate that our fixtures are documented in `pytest --fixtures`."""
        res = testdir.runpytest("--fixtures")

        res.stdout.fnmatch_lines(
            [
                "papermill_execute -- */pytest_iovis/_subplugins/papermill_runner.py:*",
                "    Return a Callable[[][[]], NotebookNode] that runs a notebook."
                + " Configurable with papermill_* fixtures.",
                "",
                "papermill_parameters -- */pytest_iovis/_subplugins/papermill_runner.py:*",
                "    Return a dictionary used to parameterize a Jupyter Notebook with Papermill.",
                "",
                "papermill_output_path -- */pytest_iovis/_subplugins/papermill_runner.py:*",
                "    Return the path to write the notebook output to.",
                "",
                "papermill_extra_arguments -- */pytest_iovis/_subplugins/papermill_runner.py:*",
                "    Return a list passed as the extra_arguments parameter for papermill.execute_notebook.",
                "",
                "papermill_cwd -- */pytest_iovis/_subplugins/papermill_runner.py:*",
                "    Return the path to execute notebooks from. Defaults to notebook's directory.",
                "",
            ],
            consecutive=True,
        )

    def test_papermill_parameters(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Validate that papermill_parameters fixture is a dictionary."""
        testdir.makeconftest(
            """
            import pytest

            def test_fixture(notebook_path, papermill_parameters):
                assert isinstance(papermill_parameters, dict)

            def pytest_iovis_set_tests():
                yield test_fixture
        """
        )

        res = testdir.runpytest(dummy_notebook)

        res.assert_outcomes(passed=1)

        assert res.ret == 0, "pytest exited non-zero exitcode"

    def test_papermill_output_path(self, testdir: pytest.Testdir, dummy_notebook: Path) -> None:
        """Validate that papermill_output_path defaults to a test specific temporary file."""
        testdir.makeconftest(
            f"""
            from pathlib import Path

            import pytest

            def test_fixture(tmp_path: Path, papermill_output_path: Path):
                assert papermill_output_path.is_absolute(), "notebook_path should be an absolute path"
                assert tmp_path in papermill_output_path.parents, "papermill_output_path should be in a temp directory"
                assert papermill_output_path.name == {dummy_notebook.with_suffix('.output.ipynb').name!r}

            def pytest_iovis_set_tests():
                yield test_fixture
        """
        )

        res = testdir.runpytest(dummy_notebook)

        res.assert_outcomes(passed=1)

        assert res.ret == 0, "pytest exited non-zero exitcode"

    def test_papermill_extra_arguments(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Validate that papermill_parameters fixture is a list."""
        testdir.makeconftest(
            """
            import pytest

            def test_fixture(notebook_path, papermill_extra_arguments):
                assert isinstance(papermill_extra_arguments, list)

            def pytest_iovis_set_tests():
                yield test_fixture
        """
        )

        res = testdir.runpytest(dummy_notebook)

        res.assert_outcomes(passed=1)

        assert res.ret == 0, "pytest exited non-zero exitcode"

    def test_papermill_cwd(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Validate that papermill_cwd defaults to the directory the notebook is in."""
        testdir.makeconftest(
            """
            import pytest

            def test_fixture(notebook_path, papermill_cwd):
                assert papermill_cwd == notebook_path.parent

            def pytest_iovis_set_tests():
                yield test_fixture
        """
        )

        res = testdir.runpytest(dummy_notebook)

        res.assert_outcomes(passed=1)

        assert res.ret == 0, "pytest exited non-zero exitcode"


class TestRunner:
    @pytest.fixture()
    def testdir(self, testdir: pytest.Testdir, monkeypatch: pytest.MonkeyPatch) -> pytest.Testdir:
        monkeypatch.setenv("IPYTHONDIR", str(Path(testdir.tmpdir, ".ipython")))
        return testdir

    @pytest.fixture()
    def dummy_notebook_raise_exc(self, dummy_notebook_factory: Callable[[Optional[PathType]], Path]) -> Path:
        nb_path = dummy_notebook_factory("assert_false")

        with nb_path.open() as f:
            nb = json.load(f)

        nb["cells"] = [
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "26ae4394",
                "metadata": {},
                "outputs": [],
                "source": ["assert False"],
            }
        ]

        with nb_path.open("w") as f:
            json.dump(nb, f)

        return nb_path

    def test_default_test_function_runs_successfully(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Validate that the default test function runs a notebook successfully."""
        res = testdir.runpytest(dummy_notebook, "-v")

        res.assert_outcomes(passed=1)

        res.stdout.fnmatch_lines("test_default_test_function_runs_successfully.ipynb::test_notebook_runs PASSED*")

    def test_papermill_exception_formatting(
        self, dummy_notebook_raise_exc: Path, testdir: pytest.Testdir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validate that papermill exceptions fully replace pytest's exception tracebacks."""
        monkeypatch.setenv("COLUMNS", "75")
        res = testdir.runpytest(dummy_notebook_raise_exc)
        res.assert_outcomes(failed=1)

        res.stdout.fnmatch_lines(
            [
                "================================ FAILURES =================================",
                "___________________________ test_notebook_runs ____________________________",
                "---------------------------------------------------------------------------",
                "AssertionError                            Traceback (most recent call last)",
                "Cell In[1], line 1",
                "----> 1 assert False",
                "",
                "AssertionError: ",
                "",
                "assert_false.ipynb:cell 1: AssertionError",
                "-------------------------- Captured stderr call ---------------------------",
            ],
            consecutive=True,
        )
