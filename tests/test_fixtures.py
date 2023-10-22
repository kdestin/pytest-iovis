from pathlib import Path

import pytest


def test_documentation(testdir: pytest.Testdir) -> None:
    """Validate that our fixtures are documented in `pytest --fixtures`."""
    res = testdir.runpytest("--fixtures")

    res.stdout.fnmatch_lines(
        [
            "notebook_path -- */pytest_papermill/_fixtures.py:*",
            "    Return the path to the notebook under test.",
            "",
        ],
        consecutive=True,
    )


def test_notebook_path(testdir: pytest.Testdir) -> None:
    notebook_path = Path("notebooks", "test.ipynb")
    testdir.makefile("ipynb", **{str(notebook_path): ""})
    testdir.makepyfile(
        f"""
        from pathlib import Path

        import pytest

        @pytest.mark.notebook({str(notebook_path)!r})
        def test_fixture(notebook_path: Path):
            assert notebook_path.is_absolute(), "notebook_path should be an absolute path"
            assert notebook_path == Path({str(testdir.tmpdir)!r}, {str(notebook_path)!r})
    """
    )

    res = testdir.runpytest("test_notebook_path.py")

    res.assert_outcomes(passed=1)

    assert res.ret == 0, "pytest exited non-zero exitcode"
