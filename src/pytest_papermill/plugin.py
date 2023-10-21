import sys

import pytest

from . import _fixtures
from ._subplugins import IPythonMarkupPlugin, JupyterNotebookDiscoverer, NotebookGrouper, NotebookMarkerHandler


def pytest_configure(config: pytest.Config) -> None:
    """Register sub-plugins."""
    # The name of this plugin
    plugin_name = config.pluginmanager.get_name(sys.modules[__name__])

    config.pluginmanager.register(_fixtures)
    config.pluginmanager.register(IPythonMarkupPlugin(), name=f"{plugin_name}.{IPythonMarkupPlugin.PLUGIN_NAME}")
    config.pluginmanager.register(
        JupyterNotebookDiscoverer(), name=f"{plugin_name}.{JupyterNotebookDiscoverer.PLUGIN_NAME}"
    )
    config.pluginmanager.register(NotebookMarkerHandler(), name=f"{plugin_name}.{NotebookMarkerHandler.PLUGIN_NAME}")
    config.pluginmanager.register(NotebookGrouper(), name=f"{plugin_name}.{NotebookGrouper.PLUGIN_NAME}")
