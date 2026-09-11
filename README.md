# XLIFF Translator

A local Windows application for translating XLIFF 1.2 files using Meta's NLLB translation model.

XLIFF Translator is designed with a strong focus on **preserving the original XLIFF/XML structure**. It translates textual content while keeping the original source content, element hierarchy, attributes, IDs, and inline elements intact.

The application also supports **Do Not Translate (DNT)** terms, allowing specific words, phrases, product names, technical terms, or other content to remain unchanged during translation.

---

# Part I — Customer / End User

## What is XLIFF Translator?

XLIFF Translator allows you to translate XLIFF 1.2 files locally on your Windows computer.

You provide:

* An XLIFF `.xlf` or `.xliff` file
* One or more target languages
* Optional Do Not Translate (DNT) terms

The application produces translated XLIFF files that preserve the structure of the original file.

Translation is performed locally. The customer does not need to install Python, PyTorch, Git, Hugging Face, or any other development dependency.

## Installation

The customer receives:

```text
XLIFF-Translator-Setup.exe
```

Run the installer and follow the installation wizard.

The installer creates the XLIFF Translator application and shortcuts.

After installation, launch **XLIFF Translator** from the Start Menu or desktop shortcut if one was created.

No separate Python installation or command-line setup is required.

## Using the application

After launching XLIFF Translator:

1. Select or drag-and-drop an XLIFF file into the application.
2. Select the target language or languages.
3. Enter any DNT terms that must remain unchanged.
4. Optionally upload a `.txt` DNT list.
5. Start the translation.
6. Download or access the generated translated XLIFF files.

The application handles the translation and XLIFF reconstruction automatically.

The underlying local server and translation model are implementation details and do not require customer configuration.

## Supported languages

The current application interface provides:

* French
* German
* English

The translation engine is based on NLLB and the application architecture supports language-specific translation codes.

## Do Not Translate (DNT)

DNT terms are words or phrases that must not be translated.

For example:

```text
START
RFLP
3DEXPERIENCE
True
False
Congratulations!
```

Enter one term per line.

Blank lines are ignored.

For example, if:

```text
Congratulations!
```

is protected, the following source:

```text
Congratulations! You have completed this lesson.
```

can produce:

```text
Congratulations! Vous avez terminé cette leçon.
```

The surrounding sentence is translated while the protected term is restored unchanged.

DNT matching is designed to protect the specified terms without unnecessarily protecting similar text inside other words.

If a protected term cannot be safely preserved, the application fails the translation rather than silently changing the protected term.

## DNT `.txt` files

Instead of entering DNT terms manually, you can provide a plain-text `.txt` file.

Example:

```text
START
RFLP
3DEXPERIENCE
True
False
Logical connections
Congratulations!
```

Use one term per line.

The application combines the uploaded DNT terms with terms entered directly in the interface.

## Output files

Translated files are stored under the user's Documents directory:

```text
Documents\
└── XLIFF Translator\
    └── outputs\
        └── <translation-job>\
            └── translated-file.fra_Latn.xlf
```

The exact output filename and language code depend on the input file and selected target language.

The original input file is not modified.

## Local processing

XLIFF translation is performed locally by the installed application.

The customer does not need to configure:

* Python
* pip
* Git
* Hugging Face
* PyTorch
* FastAPI
* Uvicorn
* A local server
* A model download

The required NLLB model is bundled with the customer application.

## XLIFF/XML preservation

XLIFF Translator does not translate or modify the original `<source>` content.

The target is constructed from the source structure and only the textual values are replaced with translated text.

The following are preserved structurally:

* XML element hierarchy
* Element names
* Attributes
* Translation-unit IDs
* Inline elements
* Element ordering
* Original source content

The application validates the reconstructed XLIFF structure before producing the final output.

The application does not promise byte-for-byte preservation of the original XML serialization. XML serialization may normalize insignificant formatting such as whitespace.

## Important limitation

The application currently focuses on **XLIFF 1.2**.

The customer should provide valid XLIFF 1.2 files.

---

# Part II — Developer Documentation

## Architecture

The project consists of several layers:

```text
XLIFF file
    │
    ▼
XLIFF parser / structural analysis
    │
    ▼
Text extraction
    │
    ▼
DNT protection
    │
    ▼
NLLB translation
    │
    ▼
DNT restoration
    │
    ▼
Target reconstruction
    │
    ▼
Structural validation
    │
    ▼
Translated XLIFF
```

The core design principle is:

> **Translate textual content without changing the structural representation of the XLIFF document.**

The original `<source>` content is treated as immutable.

## Developer project structure

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
│   ├── test_reconstruction.py
│   └── ...
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
        │
        └── static/
            ├── index.html
            ├── app.js
            └── style.css
```

## Core modules

### `core.py`

Responsible for the XLIFF/XML side of the application.

Its responsibilities include:

* Parsing XLIFF
* Extracting translatable text
* Preserving inline XML elements
* Reconstructing target content
* Replacing or creating `<target>` elements
* Validating the reconstructed document
* Writing the resulting XLIFF

The core module is intentionally independent of the NLLB model.

### `dnt.py`

Contains the Do Not Translate implementation.

It handles:

* DNT term loading
* Manual DNT terms
* `.txt` DNT lists
* Term matching
* Boundary-aware matching
* Longest-term-first processing

DNT terms are treated as protected text and must be restored exactly after translation.

### `nllb.py`

Contains the NLLB translation engine.

The current customer build uses:

```text
facebook/nllb-200-distilled-600M
```

The model supports CPU and NVIDIA CUDA execution.

The translation implementation also handles the possibility that the translation model modifies whitespace inside protected placeholders. Placeholder detection therefore has additional normalization logic so that protected DNT terms can still be restored correctly.

### `pipeline.py`

Coordinates the complete translation workflow.

Conceptually:

```text
XLIFF
  ↓
Extract text
  ↓
Apply DNT protection
  ↓
Translate with NLLB
  ↓
Restore DNT
  ↓
Reconstruct target
  ↓
Validate
  ↓
Write XLIFF
```

This is the main integration layer between the XLIFF engine and translation engine.

### `web/app.py`

Contains the FastAPI application used by the GUI.

It handles:

* XLIFF uploads
* DNT input
* DNT `.txt` uploads
* Target-language selection
* Translation requests
* Job/output management
* Downloading translated files

In the customer build, the application also resolves the bundled NLLB model and stores customer-generated data under:

```text
Documents\XLIFF Translator
```

### `web/static/`

Contains the frontend:

```text
index.html
app.js
style.css
```

The frontend communicates with the FastAPI backend running locally.

### `desktop.py`

This is the customer application launcher.

It hides the development infrastructure from the customer.

At runtime it:

1. Starts the local FastAPI/Uvicorn application.
2. Finds an available local port.
3. Waits for the server to become ready.
4. Finds Microsoft Edge or Google Chrome.
5. Opens the application in application-window mode.
6. Uses a dedicated browser profile.
7. Waits for the application window to close.
8. Shuts down the local server.

The customer therefore interacts with what appears to be a normal desktop application rather than manually starting a web server.

## Developer setup

The developer environment uses Python.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

The NLLB model can be downloaded for development when required.

The default development model is:

```text
facebook/nllb-200-distilled-600M
```

## Running the development GUI

From the project root:

```powershell
python -m uvicorn xliff_translator.web.app:app --reload
```

The development GUI is available at:

```text
http://127.0.0.1:8000
```

This development workflow is different from the customer workflow.

The customer does **not** run Uvicorn manually.

## Command-line interface

The CLI remains available as a developer utility.

Inspect an XLIFF file without loading the translation model:

```powershell
python -m xliff_translator inspect input.xlf
```

Translate:

```powershell
python -m xliff_translator translate input.xlf --langs fr,de --output-dir output
```

Use CUDA:

```powershell
python -m xliff_translator translate input.xlf --langs fr --device cuda --output-dir output
```

Use CPU:

```powershell
python -m xliff_translator translate input.xlf --langs fr --device cpu --output-dir output
```

Specify the model:

```powershell
python -m xliff_translator translate input.xlf --langs fr --model facebook/nllb-200-distilled-600M --output-dir output
```

## GPU development check

Check the NVIDIA driver and GPU:

```powershell
nvidia-smi
```

Check whether PyTorch can access CUDA:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

CUDA is optional. The application can run on CPU.

## Testing

Run the complete test suite:

```powershell
python -m pytest -q
```

The tests cover areas including:

* DNT behavior
* DNT preservation
* XLIFF reconstruction
* Structural preservation
* Translation pipeline behavior

Tests should be run before creating a customer release.

## Packaging architecture

The customer build uses PyInstaller.

The packaging flow is:

```text
Source code
    +
NLLB 600M model
    │
    ▼
PyInstaller
    │
    ▼
Standalone Windows application
    │
    ▼
Inno Setup
    │
    ▼
XLIFF-Translator-Setup.exe
```

The PyInstaller build bundles the application dependencies and the NLLB model.

The customer therefore does not need Python or the model separately.

## Bundled model

The packaging model is stored at:

```text
packaging\
└── model\
    └── nllb-200-distilled-600M\
```

The model must contain the required model and tokenizer files, including:

```text
config.json
pytorch_model.bin
sentencepiece.bpe.model
```

The build script validates these files before creating the executable.

The model is intentionally bundled rather than downloaded by the customer.

## Building the customer application

The main build script is:

```text
packaging\build.ps1
```

Run it from PowerShell:

```powershell
.\packaging\build.ps1
```

The script:

1. Locates the developer virtual environment.
2. Installs project dependencies.
3. Installs the packaging dependencies.
4. Downloads the NLLB model if it is missing or incomplete.
5. Validates the model.
6. Removes previous PyInstaller build artifacts.
7. Runs PyInstaller.
8. Validates that the model was actually bundled.
9. Reports the final application location.

The resulting customer application is:

```text
dist\
└── XLIFF Translator\
    ├── XLIFF Translator.exe
    └── _internal\
        └── model\
            └── nllb-200-distilled-600M\
```

The `_internal` directory is part of the packaged application and should not be manually modified.

## Building the installer

After a successful PyInstaller build, compile:

```text
packaging\installer.iss
```

using Inno Setup.

The resulting installer is:

```text
packaging\
└── installer-output\
    └── XLIFF-Translator-Setup.exe
```

This is the file intended for customer distribution.

The installer packages the PyInstaller application, including its `_internal` runtime and bundled model.

