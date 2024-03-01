import inspect
from pathlib import Path
from typing import Callable, Dict, Optional

import pytest

from pytest_iovis import PathType, TestObject


def override_test_functions(
    testdir: pytest.Testdir,
    *funcs: TestObject,
    inherit: bool = False,
    tests_for: Optional[Dict[str, Callable[..., object]]] = None,
    directory: Optional[PathType] = None,
) -> None:
    """Override the test functions used when collecting noteboks.

    :param pytest.Testdir testdir: The testdir fixture
    :param Callable *funcs: The test functions to use. Must be inspectable by inspect.getsource and have a
                             __name__
    :keyword inherit: Whether to inherit test functions from the parent scope
    :type inherit: bool
    :keyword tests_for: Map of files to hook functions, used to configure test functions for that file
    :type tests_for: Optional[Dict[str, Callable[..., object]]]
    :keyword directory: The directory to write the conftest.py to
    :type directory: Optional[PathType]
    """
    if tests_for is None:
        tests_for = {}

    conftest = "\n".join(
        [
            *[inspect.getsource(f).lstrip() for f in funcs],
            "",
            *[inspect.getsource(f).lstrip() for f in tests_for.values()],
            "def pytest_iovis_set_tests(current_tests, tests_for):",
            f"   if {inherit!r}:",
            "      yield from current_tests",
            *[f"   tests_for({k!r})({v.__name__})" for k, v in tests_for.items()],
            f"   yield from ({','.join([*(f.__name__ for f in funcs), ''])})",
        ]
    )

    if directory is None:
        testdir.makeconftest(conftest)
    else:
        testdir.makepyfile(**{f"{Path(directory, 'conftest')}": conftest})


@pytest.fixture()
def testdir(testdir: pytest.Testdir, monkeypatch: pytest.MonkeyPatch) -> pytest.Testdir:
    """Return the testdir fixture, but ensure that the grouping subplugin is disabled and doesn't affect output."""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p no:iovis.papermill_runner")
    return testdir


def test_notebooks_collected(testdir: pytest.Testdir, dummy_notebook: Path) -> None:
    """Validate that Jupyter Notebooks are collected as pytest.Items."""
    res = testdir.runpytest("--collect-only", dummy_notebook)

    outcomes = res.parseoutcomes()
    num_collected_tests = outcomes.get("tests", outcomes.get("test", 0))

    assert num_collected_tests == 1, f"Unexpected collected {num_collected_tests!r} tests"
    res.stdout.fnmatch_lines(f"*{test_notebooks_collected.__name__}.ipynb>*")


class TestSetTestFunctions:
    """A set of tests that validate the simplest scenarios of a user setting tests for a single scope."""

    def test_can_set_no_tests(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Validate that a user can disable collection by setting no test functions."""
        override_test_functions(testdir, *[])

        res = testdir.runpytest("-v", dummy_notebook)

        res.assert_outcomes()  # Assert that nothing is run

    def test_set_one_test(self, dummy_notebook: Path, testdir: pytest.Testdir) -> None:
        """Validate that a user can provide a test function for collection."""

        def test_function(notebook_path: object) -> None:  # noqa: ARG001
            pass

        override_test_functions(testdir, test_function)

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=1)
        res.stdout.fnmatch_lines(f"{dummy_notebook.name}::test_function*")

    def test_can_set_many_tests(
        self, testdir: pytest.Testdir, dummy_notebook_factory: Callable[[Optional[PathType]], Path]
    ) -> None:
        """Validate that a user can provide many test functions for collection."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        override_test_functions(testdir, test_function1, test_function2, test_function3)

        notebook1 = dummy_notebook_factory("test_can_override_with_many1")
        notebook2 = dummy_notebook_factory("test_can_override_with_many2")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=6)
        res.stdout.fnmatch_lines(
            [
                f"{notebook1.name}::test_function1*",
                f"{notebook1.name}::test_function2*",
                f"{notebook1.name}::test_function3*",
                f"{notebook2.name}::test_function1*",
                f"{notebook2.name}::test_function2*",
                f"{notebook2.name}::test_function3*",
            ]
        )

    def test_set_test_class(self, testdir: pytest.Testdir, dummy_notebook: Path) -> None:
        """Validate that a user can provide a test class for collection."""

        class TestClass:
            def test_function1(self, notebook_path: object) -> None:
                pass

            def test_function2(self, notebook_path: object) -> None:
                pass

            def test_function3(self, notebook_path: object) -> None:
                pass

        override_test_functions(testdir, TestClass)

        res = testdir.runpytest("-v", dummy_notebook)

        res.assert_outcomes(passed=3)

        res.stdout.fnmatch_lines(
            [
                "",
                "test_set_test_class.ipynb::TestClass::test_function1 PASSED*",
                "test_set_test_class.ipynb::TestClass::test_function2 PASSED*",
                "test_set_test_class.ipynb::TestClass::test_function3 PASSED*",
                "",
            ],
            consecutive=True,
        )


class TestCascadingConfiguration:
    """A set of tests that validate the behavior of a user configuring tests for multiple, nested scopes."""

    def test_nested_add_new_function(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that a nested conftest can add a new test to the parent conftest's set tests."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        override_test_functions(testdir, test_function1, test_function2)
        override_test_functions(testdir, test_function3, inherit=True, directory="nested")

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("nested/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=5)
        res.stdout.fnmatch_lines_random(
            [
                "test.ipynb::test_function1*",
                "test.ipynb::test_function2*",
                "nested/test.ipynb::test_function1*",
                "nested/test.ipynb::test_function2*",
                "nested/test.ipynb::test_function3*",
            ]
        )

    def test_nested_can_override(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that a nested conftest can define its own set of tests to run."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        override_test_functions(testdir, test_function1, test_function2)
        override_test_functions(testdir, test_function3, directory="nested")

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("nested/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=3)
        res.stdout.fnmatch_lines_random(
            [
                "test.ipynb::test_function1*",
                "test.ipynb::test_function2*",
                "nested/test.ipynb::test_function3*",
            ]
        )

    def test_nested_disable_collection(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that a nested conftest can completely disable collection for a directory."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        override_test_functions(testdir, test_function1, test_function2)
        override_test_functions(testdir, directory="nested")

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
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
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

        override_test_functions(testdir, test_function)
        override_test_functions(testdir, test_function1, inherit=True, directory="nested1")
        override_test_functions(testdir, test_function2, inherit=True, directory="nested1/nested2")
        override_test_functions(testdir, test_function3, inherit=True, directory="nested1/nested2/nested3")
        override_test_functions(testdir, test_function4, inherit=True, directory="nested1/nested2/nested3/nested4")

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("nested1/test.ipynb")
        dummy_notebook_factory("nested1/nested2/test.ipynb")
        dummy_notebook_factory("nested1/nested2/nested3/test.ipynb")
        dummy_notebook_factory("nested1/nested2/nested3/nested4/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=15)
        res.stdout.fnmatch_lines_random(
            [
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
            ]
        )

    def test_nested_multiple_branches_with_conftest(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that test functions can be configured simultaneously for multiple branches in a filesystem."""

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

        override_test_functions(testdir, test_function)
        override_test_functions(testdir, test_function1, directory="foo")
        override_test_functions(testdir, test_function2, directory="foo/bar", inherit=True)
        override_test_functions(testdir, test_function3, directory="baz", inherit=True)
        override_test_functions(testdir, test_function4, directory="grault/garply/waldo/fred", inherit=True)

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("foo/test.ipynb")
        dummy_notebook_factory("foo/bar/test.ipynb")
        dummy_notebook_factory("baz/test.ipynb")
        dummy_notebook_factory("grault/garply/waldo/fred/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=8)
        res.stdout.fnmatch_lines_random(
            [
                "test.ipynb::test_function PASSED*",
                "baz/test.ipynb::test_function PASSED*",
                "baz/test.ipynb::test_function3 PASSED*",
                "foo/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function2 PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_function PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_function4 PASSED*",
            ]
        )

    def test_nested_some_branches_no_conftest(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that configuring test functions in a subdirectory doesn't poison non-configured branches."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        override_test_functions(testdir, test_function1, directory="foo")
        override_test_functions(testdir, test_function2, directory="foo/bar", inherit=True)

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("foo/test.ipynb")
        dummy_notebook_factory("foo/bar/test.ipynb")
        dummy_notebook_factory("baz/test.ipynb")
        dummy_notebook_factory("grault/garply/waldo/fred/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=6)
        res.stdout.fnmatch_lines_random(
            [
                "test.ipynb::test_nothing PASSED*",
                "baz/test.ipynb::test_nothing PASSED*",
                "foo/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function1 PASSED*",
                "foo/bar/test.ipynb::test_function2 PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_nothing PASSED*",
            ]
        )


class TestFileHook:
    """A set of tests that validates that a user can provide a callback used to register tests for a specific file."""

    def test_file_hook(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that you can call a 'file hook' to configure test functions for a single file."""

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function

        override_test_functions(testdir, inherit=True, tests_for={"foo/bar/test.ipynb": file_hook})

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("foo/test.ipynb")
        dummy_notebook_factory("foo/bar/test.ipynb")
        dummy_notebook_factory("baz/test.ipynb")
        dummy_notebook_factory("grault/garply/waldo/fred/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=5)
        res.stdout.fnmatch_lines_random(
            [
                "test.ipynb::test_nothing PASSED*",
                "baz/test.ipynb::test_nothing PASSED*",
                "foo/test.ipynb::test_nothing PASSED*",
                "foo/bar/test.ipynb::test_function PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_nothing PASSED*",
            ],
        )

    def test_most_specific_file_hook_wins(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that the file hook registered in the closest conftest wins if there's multiple hooks for a file."""

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function

        def file_hook1():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function1(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function1

        def file_hook2():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function2(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function2

        def file_hook3():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function3(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function3

        override_test_functions(testdir, tests_for={"grault/garply/waldo/test.ipynb": file_hook})
        override_test_functions(testdir, directory="grault", tests_for={"garply/waldo/test.ipynb": file_hook1})
        override_test_functions(testdir, directory="grault/garply", tests_for={"waldo/test.ipynb": file_hook2})
        override_test_functions(testdir, directory="grault/garply/waldo", tests_for={"test.ipynb": file_hook3})

        dummy_notebook_factory("grault/garply/waldo/test.ipynb")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=1)
        res.stdout.fnmatch_lines(
            [
                "",
                "grault/garply/waldo/test.ipynb::test_function3 PASSED*",
                "",
            ],
            consecutive=True,
        )

    def test_file_hook_inherits_from_appropriate_scope(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that a file hook is passed the correct current_tests."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function2(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function3(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def test_function4(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def file_hook(current_tests):  # type: ignore[no-untyped-def]  # noqa: ANN001,ANN202
            def test_function5(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield from current_tests
            yield test_function5

        dummy_notebook_factory("foo/bar/test.ipynb")

        override_test_functions(
            testdir,
            test_function1,
            test_function2,
            tests_for={"foo/bar/test.ipynb": file_hook},  # Configure the file hook in the root conftest
        )

        # Override test functions one directory down
        override_test_functions(testdir, test_function3, test_function4, directory="foo/")

        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=3)
        res.stdout.fnmatch_lines(
            [
                "",
                "foo/bar/test.ipynb::test_function3 PASSED*",
                "foo/bar/test.ipynb::test_function4 PASSED*",
                "foo/bar/test.ipynb::test_function5 PASSED*",
                "",
            ],
            consecutive=True,
        )

    def test_file_hooks_for_multiple_files(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that multiple file hooks can be used to configure multiple files."""

        def test_function1(notebook_path: object) -> None:  # noqa: ARG001
            pass

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            return []

        def file_hook1():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function2(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function2

        def file_hook2(current_tests):  # type: ignore[no-untyped-def]  # noqa: ANN202,ANN001
            def test_function3(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield from current_tests
            yield test_function3

        dummy_notebook_factory("test.ipynb")
        dummy_notebook_factory("foo/bar/test.ipynb")
        dummy_notebook_factory("quux/test.ipynb")

        override_test_functions(
            testdir,
            test_function1,
            tests_for={"foo/bar/test.ipynb": file_hook},  # Configure the file hook in the root conftest
        )

        # Override test functions one directory down
        override_test_functions(
            testdir, test_function1, tests_for={"test.ipynb": file_hook, "foo/bar/test.ipynb": file_hook1}
        )
        override_test_functions(testdir, inherit=True, directory="quux", tests_for={"test.ipynb": file_hook2})
        res = testdir.runpytest("-v")

        res.assert_outcomes(passed=3)
        res.stdout.fnmatch_lines(
            [
                "",
                "foo/bar/test.ipynb::test_function2 PASSED*",
                "quux/test.ipynb::test_function1 PASSED*",
                "quux/test.ipynb::test_function3 PASSED*",
                "",
            ],
            consecutive=True,
        )

    def test_file_hook_resolves_path_relative_to_conftest(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that relative paths are resolved relative to the conftest they're provided from."""
        dummy_notebook_factory("foo/bar/baz/test.ipynb")
        dummy_notebook_factory("baz/quux/test.ipynb")
        dummy_notebook_factory("grault/garply/waldo/fred/test.ipynb")

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function

        override_test_functions(testdir, inherit=True, tests_for={"foo/bar/baz/test.ipynb": file_hook})
        override_test_functions(testdir, inherit=True, tests_for={"quux/test.ipynb": file_hook}, directory="baz")
        override_test_functions(
            testdir, inherit=True, tests_for={"waldo/fred/test.ipynb": file_hook}, directory="grault/garply/"
        )

        res = testdir.runpytest("-v")
        res.assert_outcomes(passed=3)
        res.stdout.fnmatch_lines(
            [
                "",
                "baz/quux/test.ipynb::test_function PASSED*",
                "foo/bar/baz/test.ipynb::test_function PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_function PASSED*",
                "",
            ],
            consecutive=True,
        )

    def test_file_hook_handles_absolute_paths(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that notebooks can be specified using absolute paths."""
        nb1 = dummy_notebook_factory("foo/bar/baz/test.ipynb")
        nb2 = dummy_notebook_factory("baz/quux/test.ipynb")
        nb3 = dummy_notebook_factory("grault/garply/waldo/fred/test.ipynb")

        assert all(nb.is_absolute() for nb in (nb1, nb2, nb3))

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function

        override_test_functions(testdir, inherit=True, tests_for={str(nb1): file_hook})
        override_test_functions(testdir, inherit=True, tests_for={str(nb2): file_hook}, directory="baz")
        override_test_functions(testdir, inherit=True, tests_for={str(nb3): file_hook}, directory="grault/garply/")

        res = testdir.runpytest("-v")
        res.assert_outcomes(passed=3)
        res.stdout.fnmatch_lines(
            [
                "",
                "baz/quux/test.ipynb::test_function PASSED*",
                "foo/bar/baz/test.ipynb::test_function PASSED*",
                "grault/garply/waldo/fred/test.ipynb::test_function PASSED*",
                "",
            ],
            consecutive=True,
        )

    def test_file_hook_disallows_configuring_non_subpaths(
        self,
        testdir: pytest.Testdir,
        dummy_notebook_factory: Callable[[Optional[PathType]], Path],
    ) -> None:
        """Validate that file_hook disallows configuring paths that aren't a subpath of conftest directory."""
        nb = dummy_notebook_factory("test.ipynb")

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function

        override_test_functions(testdir, inherit=True, directory="bar", tests_for={str(nb): file_hook})
        res = testdir.runpytest("-v")
        res.assert_outcomes(errors=1)
        res.stdout.fnmatch_lines(
            [
                "bar/conftest.py:10: in pytest_iovis_set_tests",
                f"    tests_for('{nb}')(file_hook)",
                "E   Failed: tests_for's path must be a subpath of the calling conftest's directory.",
                "*= short test summary info =*",
            ],
            consecutive=True,
        )

    def test_file_hook_disallows_non_existent_paths(
        self,
        testdir: pytest.Testdir,
    ) -> None:
        """Validate that file_hook disallows configuring paths that don't exist."""

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function

        override_test_functions(testdir, inherit=True, tests_for={"test.ipynb": file_hook})

        res = testdir.runpytest("-v")
        res.assert_outcomes(errors=1)
        res.stdout.fnmatch_lines(
            [
                "conftest.py:10: in pytest_iovis_set_tests",
                "    tests_for('test.ipynb')(file_hook)",
                f"E   Failed: Not a file: {Path(testdir.tmpdir, 'test.ipynb')}",
                "*= short test summary info =*",
            ],
            consecutive=True,
        )

    def test_file_hook_disallows_paths_to_non_files(
        self,
        testdir: pytest.Testdir,
    ) -> None:
        """Validate that file_hook disallows configuring paths that aren't a file."""

        def file_hook():  # type: ignore[no-untyped-def]  # noqa: ANN202
            def test_function(notebook_path: object) -> None:  # noqa: ARG001
                pass

            yield test_function

        directory = Path(testdir.tmpdir, "not_a_file")
        override_test_functions(testdir, inherit=True, tests_for={directory.name: file_hook})

        res = testdir.runpytest("-v")
        res.assert_outcomes(errors=1)
        res.stdout.fnmatch_lines(
            [
                "conftest.py:10: in pytest_iovis_set_tests",
                f"    tests_for('{directory.name}')(file_hook)",
                f"E   Failed: Not a file: {directory}",
                "*= short test summary info =*",
            ],
            consecutive=True,
        )
