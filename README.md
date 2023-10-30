# pytest-iovis

[![PyPI version](https://img.shields.io/pypi/v/pytest-iovis.svg)](https://pypi.org/project/pytest-iovis)

[![Python versions](https://img.shields.io/pypi/pyversions/pytest-iovis.svg)](https://pypi.org/project/pytest-iovis)

A plugin that lets developers leverage [pytest] to run/test [Jupyter Notebooks], with some included batteries for
getting started.

## Features

- TODO

## Requirements

- TODO

## Installation

You can install "pytest-iovis" with its default notebook runner via:

```
$ pip install 'git+https://github.com/kdestin/pytest-iovis.git[papermill]'
```

If the bundled runner is not needed:

```
$ pip install git+https://github.com/kdestin/pytest-iovis.git
```

**Note**: This does not install _any_ kernels for running notebooks. Users should install notebook kernels separately
(e.g. `pip install ipykernel`).

## Usage

- TODO

## Contributing

Contributions are very welcome. Tests can be run with
[tox](https://tox.readthedocs.io/en/latest/), please ensure the coverage
at least stays the same before you submit a pull request.

## License

Distributed under the terms of the
[MIT](http://opensource.org/licenses/MIT) license, "pytest-iovis" is
free and open source software

## Issues

If you encounter any problems, please [file an
issue](https://github.com/kdestin/pytest-iovis/issues) along with a
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


  @pytest.mark.notebook("path/to/notebook.ipynb")
  def test_notebook(tb) -> None:
      func = tb.get("func")

      assert func(1, 2) == 3
  ```

- **[pytest-notebook]** plugin uses approval/snapshot testing to guard against regressions in notebook output.

## Plugin Name

_Iovis_ is the singular [genitive case](https://en.wikipedia.org/wiki/Genitive_case) of _Iuppiter_.

Which is the Latin name of the Roman god Jupiter, from which the planet and [Jupyter Notebooks] take their namesake.

[jupyter notebooks]: https://jupyter.org/
[pytest]: https://docs.pytest.org/en/latest/
[pytest-notebook]: https://github.com/chrisjsewell/pytest-notebook
[testbook]: https://github.com/nteract/testbook
