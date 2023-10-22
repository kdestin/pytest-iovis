from pathlib import Path

import pytest


def test_documentation(testdir: pytest.Testdir) -> None:
    """Validate that our fixtures are documented in `pytest --fixtures`."""
    res = testdir.runpytest("--fixtures")

    res.stdout.fnmatch_lines(
        [
            "notebook_path -- */pytest_iovis/_fixtures.py:*",
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


def test_venv(testdir: pytest.Testdir) -> None:
    dummy_package = Path(
        testdir.makefile(
            ".toml",
            **{
                str(Path("dummy_package", "pyproject")): "\n".join(
                    [
                        "[project]",
                        'name = "dummy_package"',
                        'version = "0.0.0"',
                    ]
                )
            },
        )
    ).parent

    testdir.makepyfile(
        f"""
        import subprocess
        from typing import Iterable
        from pathlib import Path

        import pytest

        def pip_freeze() -> str:
            return subprocess.run(["pip", "freeze"], capture_output=True, text=True).stdout

        @pytest.fixture()
        def assert_pip_freeze_unchanged() -> Iterable[str]:

            freeze_before = pip_freeze()

            yield freeze_before

            freeze_after = pip_freeze()

            assert freeze_before == freeze_after

        def test_venv(assert_pip_freeze_unchanged: str, venv: Path) -> None:
            freeze_inside_venv = pip_freeze()

            assert assert_pip_freeze_unchanged == freeze_inside_venv

            subprocess.run(["pip", "install", {str(dummy_package)!r}])

            pip_freeze_after_install = pip_freeze()

            assert pip_freeze_after_install != assert_pip_freeze_unchanged
            assert {dummy_package.name!r} in pip_freeze_after_install
    """
    )

    res = testdir.runpytest("test_venv.py")

    res.assert_outcomes(passed=1)

    assert res.ret == 0, "pytest exited non-zero exitcode"
