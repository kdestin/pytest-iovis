import contextlib
import os
import site
import sys
import sysconfig
import types
import venv
from pathlib import Path
from typing import Iterator, Optional, Union, final

PathType = Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]


class ThinEnvBuilder(venv.EnvBuilder):
    """An EnvBuilder that creates "thin virtual environments".

     A "thin" virtual environment:

    * Is created with full access to packages in the host python environment (system installation or `python -m venv`)
    * Is cheap to create (in both time and space)
    * Allows for package installation, and the removal of packages that were explicitly installed into this environment

    .. example::

        ThinEnvBuilder.make_builder(with_pip=True).create(".venv")

    .. see-also::

        `QEMU's mkvenv.py script <https://gitlab.com/qemu-project/qemu/-/blob/master/python/scripts/mkvenv.py>`
    """

    @classmethod
    def make_builder(
        cls,
        *,
        clear: bool = False,
        symlinks: bool = False,
        upgrade: bool = False,
        with_pip: bool = False,
        prompt: Optional[str] = None,
    ) -> "ThinEnvBuilder":
        """Return a ThinEnvBuilder that can be used to create a virtual environment.

        See :meth:venv.EnvBuilder.__init__
        """
        child_cls = (
            ThinEnvBuilderFromVenv if ThinEnvBuilderFromVenv.is_running_in_venv() else ThinEnvBuilderFromSystemInstall
        )

        return child_cls(
            clear=clear,
            symlinks=symlinks,
            upgrade=upgrade,
            with_pip=with_pip,
            prompt=prompt,
        )

    def ensure_directories(self, env_dir: PathType) -> types.SimpleNamespace:
        """Shim the ensure_directories super method to temporarily save the environment context."""
        self._context = super().ensure_directories(env_dir)
        return self._context

    def create(self, env_dir: PathType) -> types.SimpleNamespace:  # type: ignore[override]
        super().create(env_dir)
        context = self._context
        del self._context
        return context

    @staticmethod
    @contextlib.contextmanager
    def activate(context: types.SimpleNamespace) -> Iterator[None]:
        """Activate the virtual environment.

        This temporarily prepends the virtual environment's `/bin` dir to the $PATH.

        :param types.SimpleNamespace env_dir: The virtual environment context (i.e. the return of ThinEnvBuilder.create)
        """
        original_path = os.environ.get("PATH", None)

        try:
            os.environ["PATH"] = ":".join(p for p in (context.bin_path, original_path) if p)
            yield
        finally:
            if original_path is None:
                del os.environ["PATH"]
            else:
                os.environ["PATH"] = original_path


@final
class ThinEnvBuilderFromVenv(ThinEnvBuilder):
    """An EnvBuilder that creates a thin environment from a host virtual environment created by `python -m venv`."""

    def __init__(
        self,
        *,
        clear: bool = False,
        symlinks: bool = False,
        upgrade: bool = False,
        with_pip: bool = False,
        prompt: Optional[str] = None,
    ) -> None:
        host_system_site_packages = sys.base_prefix in site.PREFIXES
        """Whether the host venv was created with system_site_packages enabled."""

        super().__init__(
            system_site_packages=host_system_site_packages,
            clear=clear,
            symlinks=symlinks,
            upgrade=upgrade,
            with_pip=with_pip,
            prompt=prompt,
        )

    def post_setup(self, context: types.SimpleNamespace) -> None:
        """Inject a `sitecustomize.py` that allows this venv to resolve packages from the host venv.

        :param types.SimpleNamespace context: The creation context

        .. see-also::

                https://docs.python.org/3/library/site.html
        """
        super().post_setup(context)

        host_lib_path = self.host_lib_path()
        current_lib_path = self.lib_path(context)
        Path(current_lib_path, "host_venv_site.pth").write_text(f"{host_lib_path}{os.linesep}", encoding="utf-8")

    @staticmethod
    def lib_path(context: types.SimpleNamespace) -> Path:
        """Fetch the environment context's directory for site-specific, not-platform-specific files.

        Compatibility wrapper for context.lib_path for Python < 3.12.

        Copied verbatim from:
            https://gitlab.com/qemu-project/qemu/-/blob/0a88ac9662950cecac74b5de3056071a964e4fc4/python/scripts/mkvenv.py#L209-237
        """
        # Python 3.12+, not strictly necessary because it's documented
        # to be the same as 3.10 code below:
        if sys.version_info >= (3, 12):
            return Path(context.lib_path)

        # Python 3.10+
        if "venv" in sysconfig.get_scheme_names():
            lib_path = sysconfig.get_path("purelib", scheme="venv", vars={"base": context.env_dir})
            assert lib_path is not None
            return Path(lib_path)

        # For Python <= 3.9 we need to hardcode this. Fortunately the
        # code below was the same in Python 3.6-3.10, so there is only
        # one case.
        if sys.platform == "win32":
            return Path(context.env_dir, "Lib", "site-packages")

        return Path(context.env_dir, "lib", "python%d.%d" % sys.version_info[:2], "site-packages")

    @staticmethod
    def host_lib_path() -> Path:
        """Fetch the host virtual environment's directory for site-specific, not-platform-specific files."""
        path = sysconfig.get_path("purelib")
        if path is None:
            raise ValueError("host venv.lib_path is unexpectedly None")
        return Path(path)

    @staticmethod
    def is_running_in_venv() -> bool:
        """Return whether this process is running in a virtual environment.

        :return: Whether we are running in a virtualenv
        :rtype: bool

        .. note::

            Python docs:

                When a Python interpreter is running from a virtual environment, sys.prefix and sys.exec_prefix point
                to the directories of the virtual environment, whereas sys.base_prefix and sys.base_exec_prefix point
                to those of the base Python used to create the environment. It is sufficient to check
                `sys.prefix != sys.base_prefix` to determine if the current interpreter is running from a
                virtual environment.

             https://docs.python.org/3/library/venv.html#how-venvs-work
        """
        return sys.prefix != sys.base_prefix


@final
class ThinEnvBuilderFromSystemInstall(ThinEnvBuilder):
    """An EnvBuilder that creates a thin environment from the system python installation."""

    def __init__(
        self,
        *,
        clear: bool = False,
        symlinks: bool = False,
        upgrade: bool = False,
        with_pip: bool = False,
        prompt: Optional[str] = None,
    ) -> None:
        super().__init__(
            system_site_packages=True,
            clear=clear,
            symlinks=symlinks,
            upgrade=upgrade,
            with_pip=with_pip,
            prompt=prompt,
        )
