from pathlib import Path

import pytest


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


def test_notebook_output_path(testdir: pytest.Testdir) -> None:
    testdir.makepyfile(
        """
        def test_fixture(tmp_path, notebook_output_path):
            assert tmp_path in notebook_output_path.parents, "notebook_output_path should be in a temporary directory"
    """
    )

    res = testdir.runpytest()

    res.assert_outcomes(passed=1)

    assert res.ret == 0, "pytest exited non-zero exitcode"
