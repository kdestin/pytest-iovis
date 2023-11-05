"""A module with miscellaneous tests for the plugin."""
import pytest


def test_subplugin_names(testdir: pytest.Testdir) -> None:
    """Verify that subplugins are registered with expected names."""
    testdir.makepyfile(
        """
        from pytest_iovis._subplugins import IPythonMarkupPlugin, JupyterNotebookDiscoverer


        def test_plugin_names(pytestconfig):
            pluginmanager = pytestconfig.pluginmanager
            assert isinstance(pluginmanager.get_plugin("iovis.notebook_discovery"), JupyterNotebookDiscoverer)
            assert isinstance(pluginmanager.get_plugin("iovis.ipython_markup"), IPythonMarkupPlugin)
        """
    )

    res = testdir.runpytest()

    res.assert_outcomes(passed=1)
