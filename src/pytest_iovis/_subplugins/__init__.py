"""A collection of small-ish 'sub-plugins'.

A pytest plugin (i.e. a _pluggy_ plugin) is a namespace that contains
implementations of predefined hook functions. A namespace can notably
be a python Module type, Class type, or an Object. Objects are
particularly interesting since they allow for state sharing across
related hooks using familiar patterns (`self.attr`). This file contains
a collection of small pytest plugins that capture a piece of the
plugin's overall functionality, and are registered in the main
plugin as follows:

.. example::

    def pytest_configure(config: pytest.Config) -> None:
        config.pluginmanager.register(SubpluginClass())

.. see-also ::

    https://pluggy.readthedocs.io/en/latest/#define-and-collect-hooks
    https://docs.python.org/3/tutorial/classes.html#tut-scopes
"""
import importlib

from .discovery import JupyterNotebookDiscoverer
from .markup import IPythonMarkupPlugin

if importlib.util.find_spec("papermill") is not None:
    from .papermill_runner import PapermillTestRunner
else:

    class PapermillTestRunner:  # type: ignore[no-redef]
        PLUGIN_NAME = "papermill_runner"


__all__ = [
    "IPythonMarkupPlugin",
    "JupyterNotebookDiscoverer",
    "PapermillTestRunner",
]
