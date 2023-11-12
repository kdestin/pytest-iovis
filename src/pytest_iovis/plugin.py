import sys

import pytest

from . import _fixtures
from ._subplugins import IPythonMarkupPlugin, JupyterNotebookDiscoverer, PapermillTestRunner


def pytest_configure(config: pytest.Config) -> None:
    """Register sub-plugins."""
    # The name of this plugin
    plugin_name = config.pluginmanager.get_name(sys.modules[__name__])

    config.pluginmanager.register(_fixtures)
    config.pluginmanager.register(JupyterNotebookDiscoverer())

    # Optional plugins that can be freely disabled
    config.pluginmanager.register(IPythonMarkupPlugin(), name=f"{plugin_name}.{IPythonMarkupPlugin.PLUGIN_NAME}")
    config.pluginmanager.register(PapermillTestRunner(), name=f"{plugin_name}.{PapermillTestRunner.PLUGIN_NAME}")
