from pathlib import Path

import pytest


def test_documentation(testdir: pytest.Testdir) -> None:
    """Validate that our fixtures are documented in `pytest --fixtures`."""
    res = testdir.runpytest("--fixtures")

    res.stdout.fnmatch_lines(
        [
            "notebook_parameters -- */pytest_papermill/_subplugins/papermill_runner.py:*",
            "    Return a dictionary used to parameterize a Jupyter Notebook with Papermill.",
            "",
            "notebook_output_path -- */pytest_papermill/_subplugins/papermill_runner.py:*",
            "    Return the path to write the notebook output to.",
            "",
            "notebook_extra_arguments [[]session scope] -- */pytest_papermill/_subplugins/papermill_runner.py:*",
            "    Return a iterable suitable to be provided as the extra_arguments parameter for "
            + "papermill.execute_notebook.",
            "",
        ],
        consecutive=True,
    )


def test_notebook_output_path(testdir: pytest.Testdir) -> None:
    notebook_path = Path("notebooks", "test.ipynb")

    testdir.makefile("ipynb", **{str(notebook_path): ""})
    testdir.makepyfile(
        f"""
        from pathlib import Path

        import pytest

        @pytest.mark.notebook({str(notebook_path)!r})
        def test_fixture(tmp_path: Path, notebook_output_path: Path):
            assert notebook_output_path.is_absolute(), "notebook_path should be an absolute path"
            assert tmp_path in notebook_output_path.parents, "notebook_output_path should be in a temporary directory"
            assert notebook_output_path.name == "test.output.ipynb"
    """
    )

    res = testdir.runpytest("test_notebook_output_path.py")

    res.assert_outcomes(passed=1)

    assert res.ret == 0, "pytest exited non-zero exitcode"


def test_default_test_function_runs_successfully(
    dummy_notebook: Path, testdir: pytest.Testdir, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate that the default test function runs a notebook successfully."""
    monkeypatch.setenv("IPYTHONDIR", str(Path(testdir.tmpdir, ".ipython")))
    res = testdir.runpytest(dummy_notebook, "-v")

    res.assert_outcomes(passed=1)

    res.stdout.fnmatch_lines("test_default_test_function_runs_successfully.ipynb::test_notebook_runs PASSED*")
