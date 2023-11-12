import os
from typing import Optional

import pytest


class IPythonMarkupPlugin:
    """Generates IPython commandline arguments that can be used to match pytest and IPython's markup settings."""

    PLUGIN_NAME = "ipython_markup"
    """A user facing name that describes this plugin"""

    def __init__(self) -> None:
        self.style_name: str = os.getenv("PYTEST_THEME", "default")
        """The pygments style name to forward to IPython. Defaults to 'default'"""
        self.should_output_color: bool = True
        """Whether to output color, or disable it. Defaults to True"""

    @pytest.hookimpl(trylast=True)
    def pytest_configure(self, config: pytest.Config) -> None:
        """Fetch the terminalreporter to determine whether to show color."""
        terminalreporter: Optional[object] = config.pluginmanager.get_plugin("terminalreporter")
        self.should_output_color = terminalreporter is not None and getattr(terminalreporter, "hasmarkup", False)

    def get_ipython_markup_arg(self) -> str:
        """Return an IPykernel argument that controls the colors used for syntax highlighting."""
        if not self.should_output_color:
            return "--InteractiveShell.colors=NoColor"

        # Up until IPython 8.15, it was not possible to configure the colorscheme used for tracebacks.
        # For IPython between 8.0.0 and 8.15.0, we monkeypatch IPython on startup to force it to use the right colors.
        # For IPython above 8.15.0, we just set the appropriate config value.
        return f"""--IPKernelApp.exec_lines=
    import IPython.core.ultratb
    from IPython import version_info
    def __set_traceback_highlighting_style():
        '''Monkeypatch get_style_by_name in ultratb for IPython>=8,<8,15'''
        from pygments.styles import get_style_by_name
        import functools
        @functools.wraps(get_style_by_name)
        def _(style: str) -> str:
            return get_style_by_name({self.style_name!r})

        IPython.core.ultratb.get_style_by_name = _

    def __set_ultra_tb_style():
        '''Use the stopgap traceback config value introduced in IPython 8.15

        .. see-also::

            https://ipython.readthedocs.io/en/stable/whatsnew/version8.html#ipython-8-15
            https://github.com/ipython/ipython/pull/14138
        '''
        from IPython import version_info

        if version_info >= (8, 15):
            from IPython.core.ultratb import VerboseTB
            VerboseTB._tb_highlight_style = {self.style_name!r}

    if (8,) <= version_info and version_info < (8, 15):
        __set_traceback_highlighting_style()
    elif (8, 15) <= version_info:
        __set_ultra_tb_style()

    del __set_traceback_highlighting_style
    del __set_ultra_tb_style
    """
