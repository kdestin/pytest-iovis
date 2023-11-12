import types
from pathlib import Path
from typing import Iterable

import pytest

from ._subplugins import JupyterNotebookDiscoverer
from ._venv_builder import ThinEnvBuilder


@pytest.fixture()
def notebook_path(request: pytest.FixtureRequest) -> Path:
    """Return the path to the notebook under test."""
    path = JupyterNotebookDiscoverer.get_notebook_path(request.node)
    if path is None:
        pytest.fail(
            f"Fixture {notebook_path.__name__!r} requested from function not managed by pytest-iovis.",
            pytrace=False,
        )

    return path


@pytest.fixture()
def venv(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterable[types.SimpleNamespace]:
    """Activate a virtual environment which has access to all packages in the host environment.

    :return: The SimpleNamespace returned by venv.VenvBuilder.ensure_directories.
    :rtype: types.SimpleNamespace
    .. see-also::
        https://docs.python.org/3/library/venv.html#venv.EnvBuilder.ensure_directories
    """
    node = request.node
    test_name = node.originalname if isinstance(node, pytest.Function) else node.name
    env_dir = tmp_path / f".venv_iovis_{test_name}"

    builder = ThinEnvBuilder.make_builder(with_pip=True)
    context = builder.create(env_dir)

    # THIS IS A HACK
    #
    # Jupyter will non-configurably replace `python`, `pythonX` or `pythonX.Y` with `sys.executable` when spawning
    # a kernel (to prevent user confusion if the Python interpreter that's running isn't the one on $PATH, like
    # when invoking a venv Python by abs path).
    #
    # See:
    #
    # https://github.com/jupyter/jupyter_client/blob/d044eb53cb64489c81ac47944a3b9e79db1dd926/jupyter_client/manager.py#L292-L303
    monkeypatch.setattr("sys.executable", context.env_exe)

    with builder.activate(context):
        yield context
