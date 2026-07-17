import os

from setuptools import setup
from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

# semble_grammars ships a compiled grammar archive per platform, so unlike a
# normal pure-Python package it needs a platform-specific wheel tag: a Linux
# user must not download the macOS archive. tools/build_wheels.py builds one
# wheel per platform by setting SEMBLE_GRAMMARS_WHEEL_PLATFORM and pruning
# the source tree down to that platform's grammar directory beforehand.
PLATFORM_WHEEL_TAGS = {
    "macos-arm64": "macosx_11_0_arm64",
    "macos-x86_64": "macosx_10_13_x86_64",
    "linux-x86_64": "manylinux2014_x86_64",
    "linux-arm64": "manylinux2014_aarch64",
    "windows-x86_64": "win_amd64",
}


class bdist_wheel(_bdist_wheel):
    """bdist_wheel that tags the wheel by OS/arch instead of "any", pinned via an env var."""

    def finalize_options(self) -> None:
        """Force a platform-specific tag and apply the requested platform override."""
        super().finalize_options()
        self.root_is_pure = False
        target = os.environ.get("SEMBLE_GRAMMARS_WHEEL_PLATFORM")
        if target:
            self.plat_name = PLATFORM_WHEEL_TAGS[target]

    def get_tag(self) -> tuple[str, str, str]:
        """Return a python-version-independent tag, keeping only the platform part."""
        _python, _abi, plat = super().get_tag()
        return "py3", "none", plat


setup(cmdclass={"bdist_wheel": bdist_wheel})
