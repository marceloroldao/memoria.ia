from __future__ import annotations

import os
from pathlib import Path

from setuptools import setup


def native_extensions():
    build_bdr = os.environ.get("MEMORIA_BUILD_BDR", "0") == "1"
    if not build_bdr:
        return [], {}

    from pybind11.setup_helpers import Pybind11Extension, build_ext

    include_dir = os.environ.get("BDR_INCLUDE_DIR")
    library_file = os.environ.get("BDR_LIBRARY_FILE")
    if not include_dir or not library_file:
        raise RuntimeError(
            "MEMORIA_BUILD_BDR=1 requires BDR_INCLUDE_DIR and BDR_LIBRARY_FILE "
            "pointing to Resolutive-DB v1.1.0 build artifacts"
        )

    library_path = Path(library_file)
    if not library_path.is_file():
        raise RuntimeError(f"BDR_LIBRARY_FILE does not exist: {library_path}")

    extensions = [
        Pybind11Extension(
            "memoria_resolutiva._bdr_native",
            ["native/bdr_atomic_pybind.cpp"],
            include_dirs=[include_dir],
            extra_objects=[str(library_path)],
            libraries=["z"],
            cxx_std=17,
            define_macros=[("PYBIND11_DETAILED_ERROR_MESSAGES", "0")],
        )
    ]
    return extensions, {"build_ext": build_ext}


ext_modules, cmdclass = native_extensions()
setup(ext_modules=ext_modules, cmdclass=cmdclass)
