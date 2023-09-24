"""A collection of small-ish 'sub-plugins' that implement the majority
of this plugin's functionality.

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
from .discovery import JupyterNotebookDiscoverer
from .markup import IPythonMarkupPlugin

__all__ = ["IPythonMarkupPlugin", "JupyterNotebookDiscoverer"]