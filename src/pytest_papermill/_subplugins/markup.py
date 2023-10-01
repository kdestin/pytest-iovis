import os
from typing import Optional

import pytest


class IPythonMarkupPlugin:
    """A pytest plugin that generates IPython commandline arguments that can be used to match pytest and IPython's
    markup settings"""

    def __init__(self) -> None:
        self.style_name: Optional[str] = os.getenv("PYTEST_THEME")
        """The pygments style name to forward to IPython. None
        means to use the default
        """
        self.should_output_color: bool = True
        """Whether to output color, or disable it. Defaults to True"""

    @pytest.hookimpl(trylast=True)
    def pytest_configure(self, config: pytest.Config) -> None:
        """Fetch the terminalreporter to determine whether to show color"""
        terminalreporter: Optional[object] = config.pluginmanager.get_plugin("terminalreporter")
        self.should_output_color = terminalreporter is not None and getattr(terminalreporter, "hasmarkup", False)

    def get_ipython_markup_arg(self) -> str:
        """Returns an IPykernel argument that controls the colors used for syntax highlighting"""

        if not self.should_output_color:
            return "--InteractiveShell.colors=NoColor"

        # The latest version of IPython, 8.5.0 at time of writing, hard codes the
        # styling for syntax highlighting when generating a traceback.
        #
        # The snippet below monkey-patches ipykernel to use the same pygments
        # style as pytest for syntax highlighting
        return f"""--IPKernelApp.exec_lines=
    def set_traceback_highlighting_style(style_name):
        from IPython import get_ipython
        from pygments.formatters import TerminalFormatter, Terminal256Formatter
        from pygments.styles import get_style_by_name
        import stack_data

        def get_records(self, etb, number_of_lines_of_context: int, tb_offset: int):
            assert etb is not None
            context = number_of_lines_of_context - 1
            after = context // 2
            before = context - after
            if self.has_colors:
                style = get_style_by_name(style_name or "monokai")
                style = stack_data.style_with_executing_node(style, "bg:ansiyellow")
                formatter = Terminal256Formatter(style=style)
            else:
                formatter = None
            options = stack_data.Options(
                before=before,
                after=after,
                pygments_formatter=formatter,
            )
            return list(stack_data.FrameInfo.stack_data(etb, options=options))[tb_offset:]

        def bind(instance, func):
            \"\"\"Binds func to instance\"\"\"
            bound_method = func.__get__(instance, instance.__class__)
            setattr(instance, func.__name__, bound_method)
            return bound_method

        bind(get_ipython().InteractiveTB, get_records)

    set_traceback_highlighting_style({self.style_name!r})
    del set_traceback_highlighting_style"""
