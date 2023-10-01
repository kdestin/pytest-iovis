import inspect
import re
import types
from typing import Optional


def make_mark_description(mark_fn: types.FunctionType) -> str:
    """Generates a string that can be used to programatically register a pytest marker from a function.

    .. example::

        def marker_name(arg1, arg2, arg3) -> None:
            \"\"\"Hello World\"\"\"

        def pytest_configure(config):
            # "marker_name(arg1, arg2, arg3): Hello World"
            config.addinivalue_line("markers", make_mark_description(notebook))

    :param types.FunctionType c: A function used to generate the marker string. The function name is used as the
        marker name, and the summary line (text before the first blank line) is used as description.
    :returns: A pytest marker definition string
    :rtype: str
    """

    def get_short_description() -> str:
        doc: Optional[str] = inspect.getdoc(mark_fn)

        if doc is None:
            return ""

        # Get the short description, which is the text before the first blankline
        short_description = re.split(r"^\s*$", doc, flags=re.MULTILINE, maxsplit=1)[0]

        # Normalize any endlines into a single line
        return re.sub("\s*\n\s*", " ", short_description).strip()

    name = mark_fn.__name__
    signature_without_return = inspect.signature(mark_fn).replace(return_annotation=inspect.Signature.empty)
    return f"{name}{signature_without_return}: {get_short_description()}"
