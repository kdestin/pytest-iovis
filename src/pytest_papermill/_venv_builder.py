import configparser
import contextlib
import os
import sys
import types
import venv
from pathlib import Path
from typing import Iterator, Optional, Union, final


class ThinEnvBuilder(venv.EnvBuilder):
    """An EnvBuilder that creates "thin virtual environments".

     A "thin" virtual environment:

    * Is created with full access to packages in the host python environment (system installation or `python -m venv`)
    * Is cheap to create (in both time and space)
    * Allows for package installation, and the removal of packages that were explicitly installed into this environment

    .. example::

        ThinEnvBuilder.make_builder(with_pip=True).create(".venv")
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

    @staticmethod
    @contextlib.contextmanager
    def activate(env_dir: Union["os.PathLike[str]", str]) -> Iterator[None]:
        """Activate the virtual environment.

        This temporarily prepends the virtual environment's `/bin` dir to the $PATH.

        :param env_dir: The path to the venv
        :type env_dir: Union[os.PathLike[str], str]
        """
        original_path = os.environ.get("PATH", None)

        try:
            os.environ["PATH"] = ":".join(p for p in (str(Path(env_dir, "bin")), original_path) if p)
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
        super().__init__(
            system_site_packages=self.host_system_site_packages(),
            clear=clear,
            symlinks=symlinks,
            upgrade=upgrade,
            with_pip=with_pip,
            prompt=prompt,
        )

    def post_setup(self, context: types.SimpleNamespace) -> None:
        """Inject a `sitecustomize.py` that allows this venv to resolve packages from the host venv.

        :param context: The creation context
        :type context: types.SimpleNamespace

        .. see-also::

                https://docs.python.org/3/library/site.html#module-sitecustomize
        """
        super().post_setup(context)
        host_env_dir = self.host_venv_path()

        if host_env_dir is None:
            raise ValueError(f"{ThinEnvBuilderFromVenv.__name__}.post_setup should only be called with an active venv")

        lib_path = Path(getattr(context, "lib_path", Path(context.env_dir, "lib")))
        host_lib_path = host_env_dir / "lib"

        site_packages_dir = Path(f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages")

        sitecustomize_path = Path(lib_path / site_packages_dir / "sitecustomize.py")
        sitecustomize_path.write_text(
            "\n".join(["import site", "", f"site.addsitedir({str(host_lib_path / site_packages_dir)!r})"])
        )

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

    @staticmethod
    def host_venv_path() -> Optional[Path]:
        """Return the path to the host virtual environment.

        :return: Path to the host virtual environment if there is an activated virtual environment, None otherwise
        :rtype: Optional[Path]
        """
        if ThinEnvBuilderFromVenv.is_running_in_venv():
            return Path(sys.prefix)

        return None

    @staticmethod
    def host_system_site_packages() -> bool:
        """Return the value of `include-system-site-packages` in the host virtual environment's pyvenv.cfg.

        :return: True if there exists a pyvenv.cfg file in the host virtual environmeent with an
            'include-system-site-packages' field that is truthy. False otherwise.
        :rtype: bool
        """
        venv_path = ThinEnvBuilderFromVenv.host_venv_path()

        if venv_path is None:
            return False

        pyvenv = Path(venv_path, "pyvenv.cfg")

        if not pyvenv.is_file():
            return False

        config = configparser.ConfigParser()

        # https://stackoverflow.com/questions/2885190/26859985#26859985
        fake_section = "hello"
        config.read_string(f"[{fake_section}]\n" + pyvenv.read_text())

        return config[fake_section].getboolean("include-system-site-packages", fallback=False)


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
