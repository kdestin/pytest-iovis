import os
from pathlib import Path
from typing import Any, Dict, Optional

import papermill as pm
import pytest

STYLE: Optional[str] = None
SHOULD_OUTPUT_COLOR: bool = True


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config):
    global STYLE
    global SHOULD_OUTPUT_COLOR
    terminalreporter: Any = config.pluginmanager.getplugin("terminalreporter")

    SHOULD_OUTPUT_COLOR = terminalreporter.hasmarkup
    STYLE = os.getenv("PYTEST_THEME")


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> Optional[pytest.Collector]:
    if file_path.suffix in [".ipynb"]:
        return JupyterNotebookFile.from_parent(parent, path=file_path)
    return None


class JupyterNotebookFile(pytest.File):
    def collect(self):
        yield JupyterNotebookTestFunction.from_parent(
            parent=self,
            name=run_note_book.__name__,
            callobj=run_note_book,
        )


class JupyterNotebookTestFunction(pytest.Function):
    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException]):
        if isinstance(excinfo.value, pm.PapermillExecutionError):
            return "\n".join(excinfo.value.traceback)
        return super().repr_failure(excinfo)


@pytest.fixture()
def notebook_parameters() -> Dict[str, Any]:
    return {}


@pytest.fixture()
def notebook_path(request: pytest.FixtureRequest) -> Path:
    return request.path


@pytest.fixture()
def notebook_output_path(notebook_path: Path) -> Path:
    """Path to output jupyter notebook with output"""
    return notebook_path.parent / f"{notebook_path.stem}.output.ipynb"


def inject_traceback_styling() -> str:
    """Returns an IPykernel argument that controls the colors used for syntax
    highlighting.
    """

    if not SHOULD_OUTPUT_COLOR:
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

set_traceback_highlighting_style({STYLE!r})
del set_traceback_highlighting_style"""


def run_note_book(notebook_path: Path, notebook_output_path: Path, notebook_parameters: Dict[str, Any]):
    pm.execute_notebook(
        notebook_path,
        notebook_output_path,
        parameters=notebook_parameters,
        extra_arguments=[inject_traceback_styling()],
    )
