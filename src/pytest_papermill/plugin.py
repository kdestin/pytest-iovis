import pytest

from . import _fixtures
from ._subplugins import IPythonMarkupPlugin, JupyterNotebookDiscoverer, NotebookMarkerHandler


def pytest_configure(config: pytest.Config) -> None:
    """Register sub-plugins"""
    config.pluginmanager.register(_fixtures)
    config.pluginmanager.register(IPythonMarkupPlugin())
    config.pluginmanager.register(JupyterNotebookDiscoverer())
    config.pluginmanager.register(NotebookMarkerHandler())
