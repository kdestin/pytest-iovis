import pytest


def test_notebooks_collected(testdir: pytest.Testdir) -> None:
    """Validate that Jupyter Notebooks are collected as pytest.Items"""

    testdir.makefile(".ipynb", "")
    res = testdir.runpytest("--collect-only")

    outcomes = res.parseoutcomes()
    num_collected_tests = outcomes.get("test", 0)

    assert num_collected_tests == 1, f"Unexpected collected {num_collected_tests!r} tests"
    res.stdout.fnmatch_lines(f"*{test_notebooks_collected.__name__}.ipynb>*")
