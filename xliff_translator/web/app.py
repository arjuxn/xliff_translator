from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..dnt import load_dnt_terms
from ..nllb import NLLBTranslator
from ..pipeline import translate_file


# ============================================================
# LANGUAGE MAPPING
# ============================================================

NLLB_LANGUAGES = {
    "en": "eng_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
}


# ============================================================
# BUILD MODE
# ============================================================

CUSTOMER_BUILD = (
    os.environ.get(
        "XLIFF_CUSTOMER_BUILD"
    )
    == "1"
)


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent

STATIC_DIR = (
    BASE_DIR
    / "static"
)


# ============================================================
# CUSTOMER MODEL LOCATION
# ============================================================

MODEL_NAME = (
    "nllb-200-distilled-600M"
)


def _find_bundled_model() -> Path:
    """
    Locate the bundled NLLB model inside a PyInstaller
    customer build.

    In a PyInstaller onedir application:

        XLIFF Translator/
        ├── XLIFF Translator.exe
        └── _internal/
            ├── model/
            │   └── nllb-200-distilled-600M/
            └── ...

    PyInstaller exposes the _internal directory through
    sys._MEIPASS at runtime.

    We therefore prefer sys._MEIPASS instead of constructing
    the path manually from sys.executable.
    """

    candidates: list[Path] = []

    # --------------------------------------------------------
    # Preferred PyInstaller runtime location.
    # --------------------------------------------------------

    meipass = getattr(
        sys,
        "_MEIPASS",
        None,
    )

    if meipass:

        candidates.append(
            Path(meipass)
            / "model"
            / MODEL_NAME
        )

    # --------------------------------------------------------
    # Normal onedir fallback.
    #
    # This protects us if _MEIPASS is unavailable for some
    # reason.
    # --------------------------------------------------------

    executable_dir = (
        Path(sys.executable)
        .resolve()
        .parent
    )

    candidates.append(
        executable_dir
        / "_internal"
        / "model"
        / MODEL_NAME
    )

    # --------------------------------------------------------
    # Additional fallback for development/testing.
    # --------------------------------------------------------

    candidates.append(
        executable_dir
        / "model"
        / MODEL_NAME
    )

    # --------------------------------------------------------
    # Return the first valid model directory.
    # --------------------------------------------------------

    for candidate in candidates:

        if candidate.is_dir():

            return candidate

    # --------------------------------------------------------
    # Return the preferred path for a useful error message.
    # --------------------------------------------------------

    if candidates:

        return candidates[0]

    raise RuntimeError(
        "Unable to determine the bundled "
        "NLLB model location."
    )


def _get_model_name(
    requested_model: str,
) -> str:
    """
    Determine which model should be used.

    Developer build:
        Use the model supplied by the UI.

    Customer build:
        Always use the bundled 600M model.

    This prevents a customer installation from attempting
    to download or locate another Hugging Face model.
    """

    if CUSTOMER_BUILD:

        bundled_model = (
            _find_bundled_model()
        )

        if not bundled_model.is_dir():

            raise RuntimeError(
                "The bundled NLLB model was not found at: "
                f"{bundled_model}"
            )

        return str(
            bundled_model
        )

    return requested_model


# ============================================================
# CUSTOMER DATA DIRECTORY
# ============================================================

if CUSTOMER_BUILD:

    DATA_DIR = (
        Path.home()
        / "Documents"
        / "XLIFF Translator"
    )

else:

    DATA_DIR = (
        BASE_DIR.parent.parent
        / "web_data"
    )


UPLOAD_DIR = (
    DATA_DIR
    / "uploads"
)

OUTPUT_DIR = (
    DATA_DIR
    / "outputs"
)


UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="XLIFF Translator",
    description=(
        "Structure-preserving XLIFF "
        "translation using NLLB."
    ),
    version="0.1.0",
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=STATIC_DIR,
    ),
    name="static",
)


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def index():

    return FileResponse(
        STATIC_DIR
        / "index.html"
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "service": "xliff-translator",
    }


# ============================================================
# LANGUAGE HELPERS
# ============================================================

def _parse_languages(
    languages: str,
) -> list[str]:
    """
    Convert the comma-separated language list received
    from the browser into NLLB language codes.
    """

    requested = [
        language.strip().lower()
        for language in languages.split(",")
        if language.strip()
    ]

    if not requested:

        raise HTTPException(
            status_code=400,
            detail=(
                "Please select at least one "
                "target language."
            ),
        )

    result: list[str] = []

    for language in requested:

        mapped = NLLB_LANGUAGES.get(
            language,
            language,
        )

        result.append(
            mapped
        )

    return result


# ============================================================
# DNT HELPERS
# ============================================================

def _normalise_typed_terms(
    dnt_terms: str,
) -> list[str]:
    """
    Parse manually entered protected terms.

    One term per line.

    Blank lines are ignored.

    Duplicate terms are removed while preserving
    the original order.
    """

    terms: list[str] = []

    seen: set[str] = set()

    for raw_line in (
        dnt_terms.splitlines()
    ):

        term = raw_line.strip()

        if not term:

            continue

        if term in seen:

            continue

        seen.add(
            term
        )

        terms.append(
            term
        )

    return terms


def _combine_dnt_sources(
    uploaded_dnt_path: Path | None,
    typed_terms: str,
    destination: Path,
) -> Path | None:
    """
    Combine the optional uploaded DNT file and manually
    entered DNT terms into one DNT file.

    Returns None when no DNT terms were supplied.
    """

    combined_terms: list[str] = []

    seen: set[str] = set()

    # --------------------------------------------------------
    # Terms from uploaded file.
    # --------------------------------------------------------

    if uploaded_dnt_path is not None:

        try:

            uploaded_terms = (
                load_dnt_terms(
                    uploaded_dnt_path
                )
            )

        except (
            FileNotFoundError,
            ValueError,
        ) as exc:

            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        for term in uploaded_terms:

            if term in seen:

                continue

            seen.add(
                term
            )

            combined_terms.append(
                term
            )

    # --------------------------------------------------------
    # Manually entered terms.
    # --------------------------------------------------------

    for term in _normalise_typed_terms(
        typed_terms
    ):

        if term in seen:

            continue

        seen.add(
            term
        )

        combined_terms.append(
            term
        )

    # --------------------------------------------------------
    # Nothing supplied.
    # --------------------------------------------------------

    if not combined_terms:

        return None

    # --------------------------------------------------------
    # Write combined DNT file.
    # --------------------------------------------------------

    destination.write_text(
        "\n".join(
            combined_terms
        )
        + "\n",
        encoding="utf-8",
    )

    return destination


# ============================================================
# TRANSLATION API
# ============================================================

@app.post("/api/translate")
async def translate(
    file: UploadFile = File(...),

    languages: str = Form(...),

    model: str = Form(
        "facebook/nllb-200-distilled-600M"
    ),

    dnt_file: UploadFile | None = File(
        default=None
    ),

    dnt_terms: str = Form(
        default=""
    ),
):

    # --------------------------------------------------------
    # Validate XLIFF.
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail=(
                "No XLIFF file was provided."
            ),
        )

    original_filename = Path(
        file.filename
    ).name

    if not original_filename.lower().endswith(
        (
            ".xlf",
            ".xliff",
        )
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload an XLF or XLIFF file."
            ),
        )

    # --------------------------------------------------------
    # Languages.
    # --------------------------------------------------------

    target_languages = (
        _parse_languages(
            languages
        )
    )

    # --------------------------------------------------------
    # Create job.
    # --------------------------------------------------------

    job_id = uuid.uuid4().hex

    job_upload_dir = (
        UPLOAD_DIR
        / job_id
    )

    job_output_dir = (
        OUTPUT_DIR
        / job_id
    )

    job_upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    job_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Save XLIFF.
    # --------------------------------------------------------

    input_path = (
        job_upload_dir
        / original_filename
    )

    with input_path.open(
        "wb"
    ) as buffer:

        shutil.copyfileobj(
            file.file,
            buffer,
        )

    # --------------------------------------------------------
    # Save uploaded DNT file if supplied.
    # --------------------------------------------------------

    uploaded_dnt_path: Path | None = None

    if dnt_file is not None:

        if not dnt_file.filename:

            raise HTTPException(
                status_code=400,
                detail=(
                    "The protected-terms file "
                    "has no filename."
                ),
            )

        dnt_filename = Path(
            dnt_file.filename
        ).name

        if not dnt_filename.lower().endswith(
            ".txt"
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Protected terms file must "
                    "be a .txt file."
                ),
            )

        uploaded_dnt_path = (
            job_upload_dir
            / dnt_filename
        )

        with uploaded_dnt_path.open(
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                dnt_file.file,
                buffer,
            )

        # ----------------------------------------------------
        # Validate uploaded DNT file.
        # ----------------------------------------------------

        try:

            load_dnt_terms(
                uploaded_dnt_path
            )

        except (
            FileNotFoundError,
            ValueError,
        ) as exc:

            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

    # --------------------------------------------------------
    # Combine uploaded + manually entered DNT terms.
    # --------------------------------------------------------

    combined_dnt_path = (
        job_upload_dir
        / "combined_dnt.txt"
    )

    try:

        dnt_path = (
            _combine_dnt_sources(
                uploaded_dnt_path=(
                    uploaded_dnt_path
                ),
                typed_terms=dnt_terms,
                destination=(
                    combined_dnt_path
                ),
            )
        )

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to process protected terms: "
                f"{exc}"
            ),
        ) from exc

    # --------------------------------------------------------
    # Resolve translation model.
    # --------------------------------------------------------

    try:

        model_path = (
            _get_model_name(
                model
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # Load translator.
    # --------------------------------------------------------

    try:

        translator = NLLBTranslator(
            model_name=model_path,
            batch_size=4,
        )

        # ----------------------------------------------------
        # Translate.
        # ----------------------------------------------------

        outputs = translate_file(
            input_path=input_path,
            output_dir=job_output_dir,
            languages=target_languages,
            translator=translator,
            dnt_path=dnt_path,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # Count protected terms.
    # --------------------------------------------------------

    dnt_count = 0

    if dnt_path is not None:

        try:

            dnt_count = len(
                load_dnt_terms(
                    dnt_path
                )
            )

        except Exception:

            dnt_count = 0

    # --------------------------------------------------------
    # Response.
    # --------------------------------------------------------

    return {
        "job_id": job_id,

        "status": "completed",

        "dnt_terms_enabled": (
            dnt_path is not None
        ),

        "dnt_terms_count": dnt_count,

        "files": [
            {
                "name": output.name,

                "url": (
                    f"/api/download/"
                    f"{job_id}/"
                    f"{output.name}"
                ),
            }

            for output in outputs
        ],
    }


# ============================================================
# DOWNLOAD
# ============================================================

@app.get(
    "/api/download/{job_id}/{filename}"
)
def download(
    job_id: str,
    filename: str,
):

    job_output_dir = (
        OUTPUT_DIR
        / job_id
    )

    # --------------------------------------------------------
    # Prevent path traversal.
    # --------------------------------------------------------

    safe_filename = Path(
        filename
    ).name

    file_path = (
        job_output_dir
        / safe_filename
    )

    if not file_path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Output file not found."
            ),
        )

    if not file_path.is_file():

        raise HTTPException(
            status_code=404,
            detail=(
                "Output file not found."
            ),
        )

    return FileResponse(
        file_path,
        filename=file_path.name,
        media_type="application/xml",
    )