# Getting Started

## Installation

You can install `pytest-iovis` with:

```shell
pip install 'pytest-iovis'
```

`pytest-iovis` optionally offers out-of-the-box support for running notebooks with [papermill], which can be enabled by
installing the `papermill` extra.

```shell
pip install 'pytest-iovis[papermill]'
```

**Note**: Installing `pytest-iovis` does not install _any_ kernels for running notebooks. Users should install the
kernels needed to run their notebooks separately (e.g. `pip install ipykernel`).

To check if the install worked, run `pytest --collect-only` from the directory that has your Jupyter Notebooks
to check that they are collected:

```console
$ pytest --collect-only
=========================== test session starts ===========================
platform linux -- Python 3.9.18, pytest-7.4.3, pluggy-1.3.0
rootdir: /home/user/repository
configfile: pyproject.toml
plugins: iovis-0.1.0
collected 1 items

<JupyterNotebookFile path/to/notebook.ipynb>
  <Function test_notebook_runs>

======================= 1 tests collected in 0.01s ========================
```

## Configuring Collected Tests

`conftest.py` is a file that configures pytest for an entire directory. You can define
[fixtures](https://docs.pytest.org/en/7.1.x/how-to/fixtures.html), or use pytest hooks to
customize pytest's behavior. See `pytest`'s documentation for more about `conftest.py`:

- https://docs.pytest.org/en/7.1.x/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files
- https://docs.pytest.org/en/7.1.x/how-to/writing_plugins.html#conftest-py-local-per-directory-plugins

`pytest-iovis` provides a custom pytest hook called `pytest_iovis_set_tests` which can be used to specify tests for
a directory:

```python
# conftest.py
from pytest_iovis import SetTestsForFileCallback, TestObject, PathType
from typing import Callable, Iterable, Optional, Tuple
from pathlib import Path


def test_foo(notebook_path: Path) -> None:
    ...


def pytest_iovis_set_tests() -> Iterable[TestObject]:
    yield test_foo
```

You can return anything that `pytest` can collect as a test from `pytest_iovis_set_tests`, a function or a class.
(**Note**: `pytest-iovis` will only collect tests named according to pytest's [naming conventions](https://docs.pytest.org/en/7.1.x/example/pythoncollection.html#changing-naming-conventions)
for functions and classes.)

The tests returned from the `pytest_iovis_set_tests` hook will be run for each notebook in the entire directory that the
`conftest.py` is present in.

### Accessing Currently Configured Tests

The `pytest_iovis_set_tests` hook provides a parameter named `current_tests`, which contains the tests that are
currently configured to run for a directory. This is useful if a root `conftest.py` sets a common set of tests, but
a nested `conftest.py` needs to add or remove tests for a specific directory.

```python
# conftest.py
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

from pytest_iovis import TestObject


def test_foo(notebook_path: Path) -> None:
    ...


def pytest_iovis_set_tests(
    current_tests: Tuple[TestObject, ...]
) -> Optional[Iterable[TestObject]]:
    yield from current_tests
    yield test_foo
```

### Configuring Test for a Specific File

`pytest_iovis_set_tests` provides a parameter `tests_for` if you need to specify tests for a specific file:

```python
# conftest.py
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

from pytest_iovis import PathType, SetTestsForFileCallback, TestObject


def test_foo(notebook_path: Path) -> None:
    ...


def pytest_iovis_set_tests(
    tests_for: Callable[[PathType], Callable[[SetTestsForFileCallback], None]],
) -> Optional[Iterable[TestObject]]:
    @tests_for("path/to/notebook.ipynb")
    def notebook_tests(current_tests: Tuple[TestObject, ...]) -> Iterable[TestObject]:
        return [test_foo]
```

The function provided to `tests_for` also accepts a `current_tests` parameter that's identical to the one from
`pytest_iovis_set_functions`.

```python
# conftest.py
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

from pytest_iovis import PathType, SetTestsForFileCallback, TestObject


def test_foo(notebook_path: Path) -> None:
    ...


def notebook_tests(current_tests: Tuple[TestObject, ...]) -> Iterable[TestObject]:
    yield from current_tests
    yield test_foo


def pytest_iovis_set_tests(
    tests_for: Callable[[PathType], Callable[[SetTestsForFileCallback], None]],
) -> Optional[Iterable[TestObject]]:
    tests_for("path/to/notebook.ipynb")(notebook_tests)
```

[papermill]: https://github.com/nteract/papermill
