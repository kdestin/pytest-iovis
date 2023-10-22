import inspect
from typing import Callable

import pytest


def test_notebooks_collected(testdir: pytest.Testdir) -> None:
    """Validate that Jupyter Notebooks are collected as pytest.Items."""
    testdir.makefile(".ipynb", "")
    res = testdir.runpytest("--collect-only")

    outcomes = res.parseoutcomes()
    num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

    assert num_collected_tests == 1, f"Unexpected collected {num_collected_tests!r} tests"
    res.stdout.fnmatch_lines(f"*{test_notebooks_collected.__name__}.ipynb>*")


class TestOverrideDefaultTestFunctions:
    @staticmethod
    def override_test_functions(testdir: pytest.Testdir, *funcs: Callable[..., object]) -> None:
        """Override the test functions used when collecting noteboks.

        :param pytest.Testdir testdir: The testdir fixture
        :param Callable *funcs: The test functions to use. Must be inspectable by inspect.getsource and have a
                                 __name__
        """
        conftest = "\n".join(
            [
                "from pytest_iovis import register_default_test_functions",
                "",
                *[inspect.getsource(f).lstrip() for f in funcs],
                "",
                "def pytest_configure(config):",
                f"   register_default_test_functions({','.join([*(f.__name__ for f in funcs), ''])}config=config)",
            ]
        )

        testdir.makeconftest(conftest)

    def test_can_override_with_nothing(self, testdir: pytest.Testdir) -> None:
        """Validate calling the register function with no test functions disables the default on."""
        testdir.makefile(".ipynb", "")

        self.override_test_functions(testdir, *[])

        res = testdir.runpytest("-v")

        res.assert_outcomes()  # Assert that nothing is run

    def test_can_replace_with_one(self, testdir: pytest.Testdir) -> None:
        """Validate that a user can replace the default test function with their own."""
        testdir.makefile(".ipynb", "")

        def test_function(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function)

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=1)
        res.stdout.fnmatch_lines("test_can_replace_with_one.ipynb::test_function*")

    def test_can_override_with_many(self, testdir: pytest.Testdir) -> None:
        """Validate that a user can replace the default test function with many others."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function1, test_function2, test_function3)
        testdir.makefile(".ipynb", **{"test_can_override_with_many1": "", "test_can_override_with_many2": ""})

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=6)
        res.stdout.fnmatch_lines(
            [
                "test_can_override_with_many1.ipynb::test_function1*",
                "test_can_override_with_many1.ipynb::test_function2*",
                "test_can_override_with_many1.ipynb::test_function3*",
                "test_can_override_with_many2.ipynb::test_function1*",
                "test_can_override_with_many2.ipynb::test_function2*",
                "test_can_override_with_many2.ipynb::test_function3*",
            ]
        )
