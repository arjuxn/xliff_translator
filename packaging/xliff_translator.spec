# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.building.build_main import Analysis
from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_submodules


# ============================================================
# PATHS
# ============================================================

PACKAGING_ROOT = Path(SPECPATH).resolve()
PROJECT_ROOT = PACKAGING_ROOT.parent

PACKAGE_ROOT = (
    PROJECT_ROOT
    / "xliff_translator"
)

STATIC_ROOT = (
    PACKAGE_ROOT
    / "web"
    / "static"
)

MODEL_ROOT = (
    PACKAGING_ROOT
    / "model"
    / "nllb-200-distilled-600M"
)

DESKTOP_SCRIPT = (
    PACKAGE_ROOT
    / "desktop.py"
)


# ============================================================
# VALIDATION
# ============================================================

if not DESKTOP_SCRIPT.exists():

    raise FileNotFoundError(
        f"desktop.py was not found: {DESKTOP_SCRIPT}"
    )


if not STATIC_ROOT.exists():

    raise FileNotFoundError(
        f"Static directory was not found: {STATIC_ROOT}"
    )


if not MODEL_ROOT.exists():

    raise FileNotFoundError(
        f"NLLB model directory was not found: {MODEL_ROOT}"
    )


# ============================================================
# BUILD DATA FILE LIST
# ============================================================

datas = []


# ============================================================
# STATIC FRONTEND FILES
# ============================================================

for source_file in STATIC_ROOT.rglob("*"):

    if source_file.is_file():

        relative_path = (
            source_file.relative_to(
                STATIC_ROOT
            )
        )

        destination_directory = (
            Path("xliff_translator")
            / "web"
            / "static"
            / relative_path.parent
        )

        datas.append(
            (
                str(source_file),
                str(destination_directory),
            )
        )


# ============================================================
# NLLB MODEL FILES
# ============================================================

for source_file in MODEL_ROOT.rglob("*"):

    if source_file.is_file():

        relative_path = (
            source_file.relative_to(
                MODEL_ROOT
            )
        )

        destination_directory = (
            Path("model")
            / "nllb-200-distilled-600M"
            / relative_path.parent
        )

        datas.append(
            (
                str(source_file),
                str(destination_directory),
            )
        )


# ============================================================
# HIDDEN IMPORTS
# ============================================================

hiddenimports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",

    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",

    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",

    "uvicorn.lifespan",
    "uvicorn.lifespan.on",

    "fastapi",
    "starlette",

    "transformers",
    "torch",
    "sentencepiece",

    "xliff_translator",
    "xliff_translator.web",
    "xliff_translator.web.app",
    "xliff_translator.core",
    "xliff_translator.dnt",
    "xliff_translator.nllb",
    "xliff_translator.pipeline",
]


# Transformers uses dynamic imports.
# Collect its submodules so the packaged application
# can load the NLLB model correctly.

hiddenimports += collect_submodules(
    "transformers"
)


# ============================================================
# ANALYSIS
# ============================================================

a = Analysis(
    [
        str(DESKTOP_SCRIPT)
    ],

    pathex=[
        str(PROJECT_ROOT)
    ],

    binaries=[],

    datas=datas,

    hiddenimports=hiddenimports,

    hookspath=[],

    hooksconfig={},

    runtime_hooks=[],

    excludes=[
        "transformers.kernels.falcon_mamba",
    ],

    noarchive=False,
)


# ============================================================
# PYZ
# ============================================================

pyz = PYZ(
    a.pure
)


# ============================================================
# EXECUTABLE
# ============================================================

exe = EXE(
    pyz,

    a.scripts,

    a.binaries,

    a.datas,

    [],

    name="XLIFF Translator",

    debug=False,

    bootloader_ignore_signals=False,

    strip=False,

    upx=False,

    console=False,
)


# ============================================================
# COLLECT
# ============================================================

coll = COLLECT(
    exe,

    a.binaries,

    a.datas,

    strip=False,

    upx=False,

    name="XLIFF Translator",
)