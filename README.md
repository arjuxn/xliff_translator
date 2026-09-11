# XLIFF Translator

XLIFF Translator is a local Windows application for translating XLIFF 1.2 files using Meta's NLLB translation model.

The main focus of the project is preserving the structure of the original XLIFF file while translating its textual content. The application also supports Do Not Translate (DNT) terms, which can be used to protect product names, technical terms, UI labels, or any other text that should remain unchanged.

The project has two main use cases:

- A packaged Windows application for end users
- A Python-based development environment for developers who need to maintain or extend the project


# End User

## What the application does

The application takes an XLIFF 1.2 file, translates its translatable text into the selected target language, and produces a new translated XLIFF file.

The application also allows specific terms to be protected from translation using DNT (Do Not Translate) terms.

For example:

```text
START
RFLP
3DEXPERIENCE
True
False
Congratulations!
````

Each term is entered on a separate line.

## Installation

The customer receives the following installer:

```text
XLIFF-Translator-Setup.exe
```

Run the installer and follow the installation steps.

After installation, XLIFF Translator can be launched from the Start Menu or from the desktop shortcut if one was created during installation.

The required translation model is bundled with the application.

## Using the application

After starting XLIFF Translator:

1. Select an XLIFF file or drag and drop one into the application.
2. Select the required target language.
3. Enter any DNT terms that should remain unchanged.
4. Optionally upload a `.txt` file containing DNT terms.
5. Start the translation.
6. Download or access the generated translated XLIFF file.

The translation and XLIFF reconstruction are handled automatically by the application.

## Supported input

The current application is designed for XLIFF 1.2 files.

Supported file extensions:

```text
.xlf
.xliff
```

The input file should be a valid XLIFF 1.2 document.

## Supported target languages

The current GUI provides:

* English
* French
* German

The translation engine uses the corresponding NLLB language codes internally.

## Do Not Translate (DNT)

DNT terms are terms that must not be translated.

For example, if the following term is protected:

```text
Congratulations!
```

and the source text is:

```text
Congratulations! You have completed this lesson.
```

the translated result can be:

```text
Congratulations! Vous avez terminé cette leçon.
```

## DNT text file

DNT terms can also be provided through a plain-text `.txt` file.

Example:

```text
START
RFLP
True
False
```

Use one term per line. Blank lines are ignored.

Terms entered directly in the GUI and terms provided through the `.txt` file are combined.

# Developer Documentation

## Project structure

The repository is organized as follows:

```text
xliff_translator/
│
├── README.md
├── CODEBASE_GUIDE.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
│
├── tests/
│   ├── fixture.xlf
│   ├── test_dnt.py
│   ├── test_dnt_integration.py
│   └── test_reconstruction.py
│
├── packaging/
│   ├── xliff_translator.spec
│   ├── build.ps1
│   ├── installer.iss
│   └── model/
│       └── nllb-200-distilled-600M/
│
└── xliff_translator/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── core.py
    ├── dnt.py
    ├── nllb.py
    ├── pipeline.py
    ├── desktop.py
    │
    └── web/
        ├── __init__.py
        ├── app.py
        └── static/
            ├── index.html
            ├── app.js
            └── style.css
```

## Main modules

### `core.py`

Handles the XLIFF/XML processing.

It is responsible for:

* Parsing XLIFF files
* Extracting translatable text
* Preserving inline elements
* Reconstructing translated target content
* Creating or replacing `<target>` elements
* Validating the reconstructed document
* Writing the resulting XLIFF file

The core XLIFF processing code does not depend directly on the NLLB model.

### `dnt.py`

Contains the Do Not Translate implementation.

It handles:

* Loading DNT terms
* Terms entered manually
* DNT `.txt` files
* Boundary-aware matching
* Longest-term-first matching
* Protection of terms before translation

DNT terms are protected before being passed to the translation model and restored after translation.

Protected terms must be restored exactly.

### `nllb.py`

Contains the NLLB translation implementation.

The current customer build uses:

```text
facebook/nllb-200-distilled-600M
```

The model supports CPU and NVIDIA CUDA execution.

The DNT implementation uses placeholders when protected terms are sent through NLLB. NLLB can sometimes modify whitespace around or inside these placeholders, so the placeholder handling includes additional logic to recognize these cases and restore the original DNT term correctly.

### `pipeline.py`

Coordinates the translation process.

It connects the XLIFF processing, DNT handling, and NLLB translation components.

The general sequence is:

1. Read the XLIFF file.
2. Extract the translatable text.
3. Protect DNT terms.
4. Translate the text using NLLB.
5. Restore the DNT terms.
6. Reconstruct the target content.
7. Validate the reconstructed XLIFF.
8. Write the translated file.

### `web/app.py`

Contains the FastAPI backend used by the GUI.

It handles:

* XLIFF uploads
* DNT input
* DNT `.txt` uploads
* Target language selection
* Translation requests
* Translation jobs
* Output files
* File downloads

For the packaged customer build, it also resolves the bundled NLLB model and uses the customer's Documents directory for generated application data.

### `web/static/`

Contains the frontend files:

```text
index.html
app.js
style.css
```

The frontend communicates with the local FastAPI application.

### `desktop.py`

This is the entry point used by the packaged Windows application.

It starts the local application automatically and opens the GUI in an application-style browser window.

The launcher:

* Finds an available local port
* Starts the FastAPI/Uvicorn server
* Waits for the server to become available
* Finds Microsoft Edge or Google Chrome
* Opens the application in application-window mode
* Uses a dedicated browser profile
* Shuts down the local server when the application window is closed

This launcher is mainly part of the customer packaging workflow. Developers can run the FastAPI application directly during development.

# Development Setup

## Python environment

The project requires Python 3.10 or newer.

Create a virtual environment from the project root:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```powershell
pip install -r requirements.txt
```

The main runtime dependencies include:

* lxml
* PyTorch
* Transformers
* SentencePiece
* Safetensors
* FastAPI
* Uvicorn
* python-multipart

## NLLB model

The default model is:

```text
facebook/nllb-200-distilled-600M
```

During development, the model can be downloaded from Hugging Face when required.

For the customer build, the model is downloaded into:

```text
packaging\
└── model\
    └── nllb-200-distilled-600M\
```

and bundled into the packaged application.

## Running the development GUI

The development GUI can be started from the project root using:

```powershell
python -m uvicorn xliff_translator.web.app:app --reload
```

Open the following address in a browser:

```text
http://127.0.0.1:8000
```

This is the development workflow only.

The customer does not start Uvicorn manually. The packaged application starts the local server through `desktop.py`.

# Command-Line Interface

The CLI is still available as a developer utility.

## Inspect an XLIFF file

The `inspect` command can be used without loading the translation model:

```powershell
python -m xliff_translator inspect input.xlf
```

## Translate using the CLI

```powershell
python -m xliff_translator translate input.xlf --langs fr,de --output-dir output
```

## Use CPU

```powershell
python -m xliff_translator translate input.xlf --langs fr --device cpu --output-dir output
```

## Use CUDA

```powershell
python -m xliff_translator translate input.xlf --langs fr --device cuda --output-dir output
```

## Specify a model

```powershell
python -m xliff_translator translate input.xlf --langs fr --model facebook/nllb-200-distilled-600M --output-dir output
```

# GPU Development

CUDA is optional. The application can run entirely on CPU.

To check the installed NVIDIA driver and GPU:

```powershell
nvidia-smi
```

To check whether PyTorch can access CUDA:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

# Testing

Run the test suite from the project root:

```powershell
python -m pytest -q
```

The tests cover the main areas of the application, including:

* DNT matching
* DNT protection and restoration
* DNT integration with translation
* XLIFF reconstruction
* XML structure preservation
* Translation pipeline behavior

Tests should be run before creating a customer build.

# Packaging

The customer application is built in two stages.

First, PyInstaller creates the standalone Windows application. The bundled application contains the Python runtime, required dependencies, application code, and NLLB model.

The resulting application is placed under:

```text
dist\
└── XLIFF Translator\
    ├── XLIFF Translator.exe
    └── _internal\
        └── model\
            └── nllb-200-distilled-600M\
```

The second stage uses Inno Setup to create the installer that is distributed to customers.

## Bundled model

The model used for the customer build is stored in:

```text
packaging\
└── model\
    └── nllb-200-distilled-600M\
```

The build script checks that the required model files exist before packaging.

At minimum, the model directory must contain:

```text
config.json
pytorch_model.bin
sentencepiece.bpe.model
```

Other tokenizer and model files required by Transformers are also included when the model is downloaded.

The model directory is ignored by Git because it is a large generated build dependency.

## Building the Windows application

The main build script is:

```text
packaging\build.ps1
```

Run it from the project root:

```powershell
.\packaging\build.ps1
```

The script handles the complete PyInstaller build process.

It:

1. Checks for the developer virtual environment.
2. Installs the project requirements.
3. Installs the packaging dependencies.
4. Downloads the NLLB model if it is missing or incomplete.
5. Validates the model files.
6. Removes previous PyInstaller output.
7. Runs PyInstaller using the project spec file.
8. Checks that the executable was created.
9. Checks that the NLLB model was bundled correctly.

The resulting executable is:

```text
dist\XLIFF Translator\XLIFF Translator.exe
```

The `_internal` directory should be treated as part of the packaged application and should not be manually edited.

## Building the installer

After successfully building the application, compile:

```text
packaging\installer.iss
```

using Inno Setup.

The installer is generated at:

```text
packaging\
└── installer-output\
    └── XLIFF-Translator-Setup.exe
```

This is the file intended for customer distribution.

The installer includes the PyInstaller application and its bundled runtime/model.

# Customer Data and Installed Files

The installed application and customer-generated data are kept separate.

The application itself is installed through the Windows installer.

Generated customer data is stored under:

```text
Documents\
└── XLIFF Translator\
```

This includes translated output files and other application-generated data.

This separation avoids relying on write permissions inside the application's installation directory.

# Git and Generated Files

The following directories and files are generated locally and should not normally be committed:

```text
.venv/
__pycache__/
.pytest_cache/
build/
dist/
packaging/installer-output/
packaging/model/
web_data/
output/
outputs/
logs/
*.log
```

The `.gitignore` file already excludes these generated files and directories.

# Important Development Notes

The XLIFF structure and DNT behavior are core requirements of the project.

Changes to the following files should therefore be made carefully:

```text
core.py
dnt.py
nllb.py
pipeline.py
```

