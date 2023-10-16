"""A module with miscelaneous tests for the plugin."""
import pytest


def test_subplugin_names(testdir: pytest.Testdir) -> None:
    """Verify that subplugins are registered with expected names."""

    testdir.makepyfile(
        """
        from pytest_papermill._subplugins import IPythonMarkupPlugin, JupyterNotebookDiscoverer, NotebookMarkerHandler


        def test_plugin_names(pytestconfig):
            pluginmanager = pytestconfig.pluginmanager
            assert isinstance(pluginmanager.get_plugin("papermill.notebook_discovery"), JupyterNotebookDiscoverer)
            assert isinstance(pluginmanager.get_plugin("papermill.ipython_markup"), IPythonMarkupPlugin)
            assert isinstance(pluginmanager.get_plugin("papermill.notebook_marker"), NotebookMarkerHandler)
        """
    )

    res = testdir.runpytest()

    res.assert_outcomes(passed=1)
