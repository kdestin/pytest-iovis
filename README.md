# pytest-iovis

A plugin that lets you use [pytest] as a frontend to run and validate [Jupyter Notebooks]. Comes with some batteries
included to get started.

```console
$ pytest notebooks/ --verbose
================================= test session starts ==================================
platform linux -- Python 3.8.18, pytest-7.4.3, pluggy-1.3.0 -- /usr/bin/python3
rootdir: /home/user/Documents/git-repository
plugins: iovis-0.1.0
collected 5 items

notebooks/bar.ipynb::test_notebook_runs PASSED                                    [1/5]
notebooks/baz.ipynb::test_notebook_runs PASSED                                    [2/5]
notebooks/foo.ipynb::test_produces_expected_output PASSED                         [3/5]
notebooks/foo.ipynb::TestMetadata::test_extra_metadata_removed PASSED             [4/5]
notebooks/foo.ipynb::TestMetadata::test_kernelspec_in_allowlist PASSED            [5/5]

================================== 5 passed in 2.63s ===================================
```

## Features

- Jupyter Notebooks are automatically discovered and run test functions that are user-configurable with directory
  specific `conftest.py` files.

Miscellaneous features that help provide a _batteries-included_ experience:

- A plugin provided default test function that uses [papermill] to run collected notebooks. This feature is optional
  and can be enabled by installing the `[papermill]` extra when installing `pytest-iovis`.
- A `venv` fixture which activates a test-specific [virtual environment](https://docs.python.org/3/library/venv.html)
  which has access to all packages from the host environment. Useful when running notebooks that target `ipykernel`
  that may try to install packages.

## Installation

You can install "pytest-iovis" with its default notebook runner via:

```
pip install 'pytest-iovis[papermill]'
```

If the bundled runner is not needed:

```
pip install 'pytest-iovis'
```

**Note**: Installing `pytest-iovis` does not install _any_ kernels for running notebooks. Users should install notebook
kernels separately (e.g. `pip install ipykernel`).

## Getting Started

See [docs/getting-started.md](./docs/getting-started.md).

## Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for instructions on how to contribute.

## Issues

If you encounter any problems, please [file an issue](https://github.com/kdestin/pytest-iovis/issues) along with a
detailed description.

## Related Projects

- **[testbook]** is a unit testing framework extension for testing code in Jupyter Notebooks.  It enables the execution
  and unit testing of code _without_ needing to modify the Jupyter Notebook itself, so that unit tests can be written
  using [unittest](https://docs.python.org/3/library/unittest.html), [pytest], or another unit testing framework.

  `testbook` and `pytest-iovis` have orthogonal goals, but happen to compliment each other fairly well. Example:

  ```python
  from testbook import testbook


  @pytest.fixture()
  def tb(notebook_path: Path):
      with testbook(notebook_path, execute=True) as tb_obj:
          yield tb_obj


  def test_notebook(tb) -> None:
      func = tb.get("func")

      assert func(1, 2) == 3


  def pytest_iovis_set_tests():
      yield test_notebook
  ```

- **[nbval]** is a [pytest] plugin that ensures that a notebook produces output matching the output stored in the
  notebook.

- **[pytest-notebook]** plugin uses approval/snapshot testing to guard against regressions in notebook output.

## Plugin Name

_Iovis_ is the singular [genitive case](https://en.wikipedia.org/wiki/Genitive_case) of _Iuppiter_.

Which is the Latin name of the Roman god Jupiter, from which the planet and [Jupyter Notebooks] take their namesake.

[jupyter notebooks]: https://jupyter.org/
[nbval]: https://github.com/computationalmodelling/nbval
[papermill]: https://github.com/nteract/papermill
[pytest]: https://docs.pytest.org/en/latest/
[pytest-notebook]: https://github.com/chrisjsewell/pytest-notebook
[testbook]: https://github.com/nteract/testbook
