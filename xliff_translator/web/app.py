from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..nllb import NLLBTranslator
from ..pipeline import translate_file


# ============================================================
# NLLB LANGUAGE MAPPING
# ============================================================

NLLB_LANGUAGES = {
    "en": "eng_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
}


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"

DATA_DIR = BASE_DIR.parent.parent / "web_data"

UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"


UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="XLIFF Translator",
    description="Structure-preserving XLIFF translation using NLLB.",
    version="0.1.0",
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=STATIC_DIR
    ),
    name="static",
)


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def index():
    return FileResponse(
        STATIC_DIR / "index.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "xliff-translator",
    }


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
):
    # --------------------------------------------------------
    # Validate uploaded file
    # --------------------------------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file was provided.",
        )

    if not file.filename.lower().endswith(
        (".xlf", ".xliff")
    ):
        raise HTTPException(
            status_code=400,
            detail="Please upload an XLF or XLIFF file.",
        )

    # --------------------------------------------------------
    # Parse requested languages
    #
    # The frontend sends:
    #
    #     fr
    #     de
    #     en
    #
    # We convert them to:
    #
    #     fra_Latn
    #     deu_Latn
    #     eng_Latn
    #
    # before passing them to NLLB.
    # --------------------------------------------------------

    requested_languages = [
        language.strip().lower()
        for language in languages.split(",")
        if language.strip()
    ]

    if not requested_languages:
        raise HTTPException(
            status_code=400,
            detail="Select at least one target language.",
        )

    # --------------------------------------------------------
    # Convert UI language codes to NLLB language codes.
    # --------------------------------------------------------

    target_languages: list[str] = []

    for language in requested_languages:
        nllb_language = NLLB_LANGUAGES.get(
            language,
            language,
        )

        target_languages.append(
            nllb_language
        )

    # --------------------------------------------------------
    # Validate that all requested languages are supported
    # by the web UI.
    #
    # If a raw NLLB code was submitted directly, we still
    # allow it. This keeps the API flexible.
    # --------------------------------------------------------

    for language in target_languages:
        if "_" not in language:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported target language: "
                    f"{language}. "
                    f"Supported languages: "
                    f"{', '.join(NLLB_LANGUAGES.keys())}."
                ),
            )

    # --------------------------------------------------------
    # Create isolated directories for this translation job.
    # --------------------------------------------------------

    job_id = uuid.uuid4().hex

    job_upload_dir = (
        UPLOAD_DIR / job_id
    )

    job_output_dir = (
        OUTPUT_DIR / job_id
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
    # Save uploaded XLIFF.
    # --------------------------------------------------------

    input_path = (
        job_upload_dir
        / Path(file.filename).name
    )

    with input_path.open(
        "wb"
    ) as buffer:
        shutil.copyfileobj(
            file.file,
            buffer,
        )

    # --------------------------------------------------------
    # Load NLLB translator.
    # --------------------------------------------------------

    translator = NLLBTranslator(
        model_name=model,
        batch_size=4,
    )

    # --------------------------------------------------------
    # Translate.
    # --------------------------------------------------------

    try:
        outputs = translate_file(
            input_path=input_path,
            output_dir=job_output_dir,
            languages=target_languages,
            translator=translator,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # Build download information.
    # --------------------------------------------------------

    return {
        "job_id": job_id,
        "status": "completed",
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
# DOWNLOAD TRANSLATED FILE
# ============================================================

@app.get(
    "/api/download/{job_id}/{filename}"
)
def download(
    job_id: str,
    filename: str,
):
    job_output_dir = (
        OUTPUT_DIR / job_id
    )

    # Use only the filename portion.
    # This prevents path traversal such as ../file.xlf.
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
            detail="Output file not found.",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Output file not found.",
        )

    return FileResponse(
        file_path,
        filename=file_path.name,
        media_type="application/xml",
    )