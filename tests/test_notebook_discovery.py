import inspect
import os
from pathlib import Path
from typing import Callable, Optional, Union

import pytest


@pytest.fixture()
def testdir(testdir: pytest.Testdir, monkeypatch: pytest.MonkeyPatch) -> pytest.Testdir:
    """Return the testdir fixture, but ensure that the grouping subplugin is disabled and doesn't affect output."""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p no:iovis.papermill_runner")
    return testdir


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
    def override_test_functions(
        testdir: pytest.Testdir,
        *funcs: Callable[..., object],
        inherit: bool = False,
        directory: Optional[Union[str, "os.PathLike[str]"]] = None,
    ) -> None:
        """Override the test functions used when collecting noteboks.

        :param pytest.Testdir testdir: The testdir fixture
        :param Callable *funcs: The test functions to use. Must be inspectable by inspect.getsource and have a
                                 __name__
        :keyword inherit: Whether to inherit test functions from the parent scope
        :type inherit: bool
        :keyword directory: The directory to write the conftest.py to
        :type directory: Optional[Union[str, "os.PathLike[str]"]]
        """
        conftest = "\n".join(
            [
                *[inspect.getsource(f).lstrip() for f in funcs],
                "",
                "def pytest_iovis_set_default_functions(inherited):",
                f"   if {inherit!r}:",
                "      yield from inherited",
                f"   yield from ({','.join([*(f.__name__ for f in funcs), ''])})",
            ]
        )

        if directory is None:
            testdir.makeconftest(conftest)
        else:
            testdir.makepyfile(**{f"{Path(directory, 'conftest')}": conftest})

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

    def test_nested_add_new_function(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path],
    ) -> None:
        """Validate that a nested conftest can add a new test to the parent conftest's set tests."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function1, test_function2)
        self.override_test_functions(testdir, test_function3, inherit=True, directory="nested")

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("nested/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=5)
        res.stdout.fnmatch_lines(
            [
                "",
                "test.ipynb::test_function1*",
                "test.ipynb::test_function2*",
                "nested/test.ipynb::test_function1*",
                "nested/test.ipynb::test_function2*",
                "nested/test.ipynb::test_function3*",
                "",
            ],
            consecutive=True,
        )

    def test_nested_can_override(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path],
    ) -> None:
        """Validate that a nested conftest can define its own set of tests to run."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function1, test_function2)
        self.override_test_functions(testdir, test_function3, directory="nested")

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("nested/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=3)
        res.stdout.fnmatch_lines(
            [
                "",
                "test.ipynb::test_function1*",
                "test.ipynb::test_function2*",
                "nested/test.ipynb::test_function3*",
                "",
            ],
            consecutive=True,
        )

    def test_nested_disable_collection(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path],
    ) -> None:
        """Validate that a nested conftest can completely disable collection for a directory."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function1, test_function2)
        self.override_test_functions(testdir, directory="nested")

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("nested/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=2)
        res.stdout.fnmatch_lines(
            [
                "",
                "test.ipynb::test_function1*",
                "test.ipynb::test_function2*",
                "",
            ],
            consecutive=True,
        )

    def test_deeply_nested(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path],
    ) -> None:
        """Validate that we can configure multiple levels of nested confttests."""

        def test_function(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function4(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function)
        self.override_test_functions(testdir, test_function1, inherit=True, directory="nested1")
        self.override_test_functions(testdir, test_function2, inherit=True, directory="nested1/nested2")
        self.override_test_functions(testdir, test_function3, inherit=True, directory="nested1/nested2/nested3")
        self.override_test_functions(testdir, test_function4, inherit=True, directory="nested1/nested2/nested3/nested4")

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("nested1/test.ipynb")
        dummy_notebook_factory("nested1/nested2/test.ipynb")
        dummy_notebook_factory("nested1/nested2/nested3/test.ipynb")
        dummy_notebook_factory("nested1/nested2/nested3/nested4/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=15)
        res.stdout.fnmatch_lines(
            [
                "",
                "test.ipynb::test_function PASSED*",
                "nested1/test.ipynb::test_function PASSED*",
                "nested1/test.ipynb::test_function1 PASSED*",
                "nested1/nested2/test.ipynb::test_function PASSED*",
                "nested1/nested2/test.ipynb::test_function1 PASSED*",
                "nested1/nested2/test.ipynb::test_function2 PASSED*",
                "nested1/nested2/nested3/test.ipynb::test_function PASSED*",
                "nested1/nested2/nested3/test.ipynb::test_function1 PASSED*",
                "nested1/nested2/nested3/test.ipynb::test_function2 PASSED*",
                "nested1/nested2/nested3/test.ipynb::test_function3 PASSED*",
                "nested1/nested2/nested3/nested4/test.ipynb::test_function PASSED*",
                "nested1/nested2/nested3/nested4/test.ipynb::test_function1 PASSED*",
                "nested1/nested2/nested3/nested4/test.ipynb::test_function2 PASSED*",
                "nested1/nested2/nested3/nested4/test.ipynb::test_function3 PASSED*",
                "nested1/nested2/nested3/nested4/test.ipynb::test_function4 PASSED*",
                "",
            ],
            consecutive=True,
        )

    def test_nested_multiple_branches_with_conftest(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path],
    ) -> None:
        """Validate that default functions can be configured simultaneously for multiple branches in a filesystem."""

        def test_function(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function4(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function)
        self.override_test_functions(testdir, test_function1, directory="foo")
        self.override_test_functions(testdir, test_function2, directory="foo/bar", inherit=True)
        self.override_test_functions(testdir, test_function3, directory="baz", inherit=True)
        self.override_test_functions(testdir, test_function4, directory="grault/garply/waldo/fred", inherit=True)

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("foo/test.ipynb")
        dummy_notebook_factory("foo/bar/test.ipynb")
        dummy_notebook_factory("baz/test.ipynb")
        dummy_notebook_factory("grault/garply/waldo/fred/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=8)
        res.stdout.fnmatch_lines(
            [
                "",
                "test.ipynb::test_function PASSED*",
                "baz/test.ipynb::test_function PASSED*",
                "baz/test.ipynb::test_function3 PASSED*",
                "foo/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function2 PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_function PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_function4 PASSED*",
                "",
            ],
            consecutive=True,
        )

    def test_nested_some_branches_no_conftest(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[Union["os.PathLike[str]", str]]], Path],
    ) -> None:
        """Validate that configuring default tests in a subdirectory doesn't poison non-configured branches."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        self.override_test_functions(testdir, test_function1, directory="foo")
        self.override_test_functions(testdir, test_function2, directory="foo/bar", inherit=True)

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("foo/test.ipynb")
        dummy_notebook_factory("foo/bar/test.ipynb")
        dummy_notebook_factory("baz/test.ipynb")
        dummy_notebook_factory("grault/garply/waldo/fred/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=6)
        res.stdout.fnmatch_lines(
            [
                "",
                "test.ipynb::test_nothing PASSED*",
                "baz/test.ipynb::test_nothing PASSED*",
                "foo/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function2 PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_nothing PASSED*",
                "",
            ],
            consecutive=True,
        )
