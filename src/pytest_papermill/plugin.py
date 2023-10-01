import pytest

from . import _fixtures
from ._subplugins import IPythonMarkupPlugin, JupyterNotebookDiscoverer


def pytest_configure(config: pytest.Config):
    """Register sub-plugins"""
    config.pluginmanager.register(_fixtures)
    config.pluginmanager.register(IPythonMarkupPlugin())
    config.pluginmanager.register(JupyterNotebookDiscoverer())
