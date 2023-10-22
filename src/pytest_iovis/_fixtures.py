from pathlib import Path
from typing import Iterable, Optional

import pytest

from ._subplugins import NotebookMarkerArg, NotebookMarkerHandler
from ._venv_builder import ThinEnvBuilder


@pytest.fixture(name=NotebookMarkerHandler.FIXTURE_NAME)
def notebook_path(request: pytest.FixtureRequest) -> Path:
    """Return the path to the notebook under test."""
    param: Optional[object] = getattr(request, "param", None)
    if not isinstance(param, NotebookMarkerArg):
        pytest.fail(
            f"Fixture {notebook_path.__name__!r} requested from function without @pytest.mark.notebook marker.",
            pytrace=False,
        )

    return param.resolved_path


@pytest.fixture()
def venv(request: pytest.FixtureRequest, tmp_path: Path) -> Iterable[Path]:
    """Activate a virtual environment and return path to the environment dir."""
    node = request.node
    test_name = node.originalname if isinstance(node, pytest.Function) else node.name
    env_dir = tmp_path / f".venv_iovis_{test_name}"

    builder = ThinEnvBuilder.make_builder(with_pip=True)
    context = builder.create(env_dir)

    with builder.activate(context):
        yield env_dir
