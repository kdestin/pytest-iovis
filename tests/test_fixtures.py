import pytest


def test_notebook_path(testdir: pytest.Testdir) -> None:
    testdir.makepyfile(
        """
        def test_fixture(notebook_path):
            assert notebook_path.is_absolute(), "notebook_path should be an absolute path"
    """
    )

    res = testdir.runpytest()

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
