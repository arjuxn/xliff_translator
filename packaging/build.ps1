$ErrorActionPreference = "Stop"


# ============================================================
# PROJECT
# ============================================================

$ProjectRoot = Resolve-Path (
    Join-Path $PSScriptRoot ".."
)

$PackagingDir = Join-Path `
    $ProjectRoot `
    "packaging"

$ModelDir = Join-Path `
    $PackagingDir `
    "model\nllb-200-distilled-600M"

$DistDir = Join-Path `
    $ProjectRoot `
    "dist"

$BuildDir = Join-Path `
    $ProjectRoot `
    "build"


Write-Host ""
Write-Host "=========================================="
Write-Host " XLIFF Translator Customer Build"
Write-Host "=========================================="
Write-Host ""


Set-Location $ProjectRoot


# ============================================================
# PYTHON
# ============================================================

$PythonPath = Join-Path `
    $ProjectRoot `
    ".venv\Scripts\python.exe"


if (-not (Test-Path $PythonPath)) {

    throw `
        "Developer virtual environment not found. Expected: $PythonPath"
}


$Python = (
    Resolve-Path $PythonPath
).Path


# ============================================================
# DEPENDENCIES
# ============================================================

Write-Host ""
Write-Host "Checking build dependencies..."

& $Python -m pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {

    throw `
        "Failed to install project requirements."
}


& $Python -m pip install `
    pyinstaller `
    huggingface_hub

if ($LASTEXITCODE -ne 0) {

    throw `
        "Failed to install packaging dependencies."
}


# ============================================================
# MODEL DIRECTORY
# ============================================================

if (-not (Test-Path $ModelDir)) {

    New-Item `
        -ItemType Directory `
        -Path $ModelDir `
        -Force `
        | Out-Null
}


# ============================================================
# MODEL FILES
# ============================================================

$ModelConfig = Join-Path `
    $ModelDir `
    "config.json"

$ModelWeights = Join-Path `
    $ModelDir `
    "pytorch_model.bin"

$ModelTokenizer = Join-Path `
    $ModelDir `
    "sentencepiece.bpe.model"


# ============================================================
# CHECK EXISTING MODEL
# ============================================================

$ModelIsValid = (
    (Test-Path $ModelConfig) -and
    (Test-Path $ModelWeights) -and
    (Test-Path $ModelTokenizer)
)


# ============================================================
# DOWNLOAD MODEL IF NECESSARY
# ============================================================

if ($ModelIsValid) {

    Write-Host ""
    Write-Host "NLLB model already exists and is valid."

}
else {

    Write-Host ""
    Write-Host "Existing NLLB model is incomplete."
    Write-Host "Removing incomplete model files..."

    if (Test-Path $ModelDir) {

        Remove-Item `
            $ModelDir `
            -Recurse `
            -Force
    }

    New-Item `
        -ItemType Directory `
        -Path $ModelDir `
        -Force `
        | Out-Null


    Write-Host ""
    Write-Host "Downloading NLLB-200 Distilled 600M..."
    Write-Host "This may take some time."
    Write-Host ""


    & $Python -c `
        "from huggingface_hub import snapshot_download; snapshot_download(repo_id='facebook/nllb-200-distilled-600M', local_dir=r'$ModelDir')"

    if ($LASTEXITCODE -ne 0) {

        throw `
            "NLLB model download failed."
    }
}


# ============================================================
# VALIDATE MODEL
# ============================================================

Write-Host ""
Write-Host "Validating NLLB model..."


if (-not (Test-Path $ModelConfig)) {

    throw `
        "NLLB model is missing config.json."
}


if (-not (Test-Path $ModelWeights)) {

    Write-Host ""
    Write-Host "pytorch_model.bin was not found."

    Write-Host ""
    Write-Host "Files currently present in the model directory:"

    Get-ChildItem `
        $ModelDir `
        -Recurse `
        -File `
        | Select-Object FullName

    throw `
        "NLLB model is incomplete: pytorch_model.bin is missing."
}


if (-not (Test-Path $ModelTokenizer)) {

    throw `
        "NLLB model is incomplete: sentencepiece.bpe.model is missing."
}


Write-Host "NLLB model validated successfully."


# ============================================================
# CLEAN PREVIOUS BUILD
# ============================================================

Write-Host ""
Write-Host "Cleaning previous PyInstaller output..."


if (Test-Path $DistDir) {

    Remove-Item `
        $DistDir `
        -Recurse `
        -Force
}


if (Test-Path $BuildDir) {

    Remove-Item `
        $BuildDir `
        -Recurse `
        -Force
}


# ============================================================
# PYINSTALLER BUILD
# ============================================================

Write-Host ""
Write-Host "Building standalone customer application..."
Write-Host ""


& $Python -m PyInstaller `
    --clean `
    --noconfirm `
    "$PackagingDir\xliff_translator.spec"


if ($LASTEXITCODE -ne 0) {

    throw `
        "PyInstaller build failed."
}


# ============================================================
# VERIFY EXE
# ============================================================

$Exe = Join-Path `
    $DistDir `
    "XLIFF Translator\XLIFF Translator.exe"


if (-not (Test-Path $Exe)) {

    throw `
        "Executable was not created."
}


# ============================================================
# VERIFY BUNDLED MODEL
# ============================================================
#
# PyInstaller 6.x onedir places collected data under:
#
#     XLIFF Translator\
#         _internal\
#             model\
#                 nllb-200-distilled-600M\
#
# ============================================================

$BundledModelDir = Join-Path `
    $DistDir `
    "XLIFF Translator\_internal\model\nllb-200-distilled-600M"

$BundledModelConfig = Join-Path `
    $BundledModelDir `
    "config.json"

$BundledModelWeights = Join-Path `
    $BundledModelDir `
    "pytorch_model.bin"

$BundledModelTokenizer = Join-Path `
    $BundledModelDir `
    "sentencepiece.bpe.model"


Write-Host ""
Write-Host "Validating bundled model..."


if (-not (Test-Path $BundledModelDir)) {

    Write-Host ""
    Write-Host "Bundled model directory was not found."

    Write-Host ""
    Write-Host "Model-related files found inside dist:"

    Get-ChildItem `
        $DistDir `
        -Recurse `
        -File `
        | Where-Object {
            $_.Name -in @(
                "config.json",
                "pytorch_model.bin",
                "sentencepiece.bpe.model"
            )
        } `
        | Select-Object FullName, Length

    throw `
        "Build completed, but the bundled model directory was not found."
}


if (-not (Test-Path $BundledModelConfig)) {

    throw `
        "Build completed, but config.json was not bundled."
}


if (-not (Test-Path $BundledModelWeights)) {

    throw `
        "Build completed, but pytorch_model.bin was not bundled."
}


if (-not (Test-Path $BundledModelTokenizer)) {

    throw `
        "Build completed, but sentencepiece.bpe.model was not bundled."
}


Write-Host "Bundled NLLB model validated successfully."


# ============================================================
# FINAL RESULT
# ============================================================

Write-Host ""
Write-Host "=========================================="
Write-Host " BUILD COMPLETE"
Write-Host "=========================================="
Write-Host ""

Write-Host "Customer application:"
Write-Host $Exe

Write-Host ""

Write-Host "Bundled model:"
Write-Host $BundledModelDir

Write-Host ""

Write-Host "Customer data directory:"
Write-Host (
    Join-Path `
        ([Environment]::GetFolderPath("MyDocuments")) `
        "XLIFF Translator"
)

Write-Host ""