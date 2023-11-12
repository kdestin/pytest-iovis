"""A module with miscellaneous tests for the plugin."""
import pytest


def test_optional_plugin_names(testdir: pytest.Testdir) -> None:
    """Verify that optional subplugins are registered with expected names."""
    testdir.makepyfile(
        """
        from pytest_iovis._subplugins import IPythonMarkupPlugin, PapermillTestRunner


        def test_plugin_names(pytestconfig):
            pluginmanager = pytestconfig.pluginmanager
            assert isinstance(pluginmanager.get_plugin("iovis.ipython_markup"), IPythonMarkupPlugin)
            assert isinstance(pluginmanager.get_plugin("iovis.papermill_runner"), PapermillTestRunner)
        """
    )

    res = testdir.runpytest()

    res.assert_outcomes(passed=1)
