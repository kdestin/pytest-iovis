import pytest


def test_notebook_marker_documentation(testdir: pytest.Testdir) -> None:
    """Check that `pytest --markers` displays a help message for @pytest.mark.notebook"""
    res = testdir.runpytest("--markers")

    res.stdout.fnmatch_lines(
        "@pytest.mark.notebook(path: Union[[]os.PathLike, str]): Associate a test function with a Jupyter Notebook."
    )

    assert res.ret == 0
