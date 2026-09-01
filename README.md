# XLIFF NLLB Translator

A local XLIFF 1.2 translation tool powered by Meta's NLLB models.

The application translates text inside XLIFF files while preserving XML structure, IDs, attributes, inline elements, and source content. It also supports user-defined Do Not Translate (DNT) terms.

## Features

- XLIFF 1.2 translation
- NLLB neural translation
- CPU and NVIDIA CUDA support
- Multiple target languages
- Browser-based GUI
- Command-line interface
- XLIFF drag-and-drop upload
- DNT terms entered directly in the GUI
- Optional `.txt` DNT list upload
- DNT preservation validation
- XML structure validation
- Downloadable translated XLIFF files
- Local processing

## Requirements

- Python 3.10+
- PyTorch
- Hugging Face Transformers
- NVIDIA GPU is optional

Default model:

`facebook/nllb-200-distilled-600M`

The first run may download the model from Hugging Face.

## Installation

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

For NVIDIA GPU use, install a CUDA-compatible PyTorch build appropriate for your system.

## Run the GUI

From the project root:

```powershell
python -m uvicorn xliff_translator.web.app:app --reload
```

Open:

`http://127.0.0.1:8000`

The GUI lets you upload an XLIFF file, select target languages and the model, enter optional DNT terms or upload a DNT `.txt` file, start translation, and download the results.

## DNT — Do Not Translate

DNT terms are terms that must remain unchanged.

Example:

```text
START
RFLP
3DEXPERIENCE
True
False
Congratulations!
```

Use one term per line. Blank lines are ignored.

If `Congratulations!` is protected, a source such as:

```text
Congratulations! You have completed this lesson.
```

can produce:

```text
Congratulations! Vous avez terminé cette leçon.
```

The surrounding text is translated while the protected term is restored exactly.

If a protected term cannot be safely preserved, the translation fails instead of silently changing the term.

## DNT text file

A DNT list can be uploaded as a plain `.txt` file:

```text
START
RFLP
3DEXPERIENCE
True
False
Logical connections
Congratulations!
```

## Command-line interface

Inspect an XLIFF without loading the translation model:

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

Specify a model:

```powershell
python -m xliff_translator translate input.xlf --langs fr --model facebook/nllb-200-distilled-600M --output-dir output
```

## GPU check

```powershell
nvidia-smi
```

Check PyTorch CUDA access:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

## XML preservation

The original `<source>` elements are not modified.

Target content is created from a copy of the source structure, with textual values replaced by translations.

The following are preserved structurally:

- XML element hierarchy
- Element names
- Attributes
- Translation-unit IDs
- Inline elements
- Ordering
- Source content

The application does not promise byte-for-byte preservation of XML serialization. XML serialization can normalize insignificant formatting.

## Project structure

```text
xliff_translator/
├── README.md
├── CODEBASE_GUIDE.md
├── pyproject.toml
├── requirements.txt
├── tests/
└── xliff_translator/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── core.py
    ├── dnt.py
    ├── nllb.py
    ├── pipeline.py
    └── web/
        ├── __init__.py
        ├── app.py
        └── static/
            ├── index.html
            ├── app.js
            └── style.css
```

## Testing

Run:

```powershell
python -m pytest -q
```

## Development artifacts

These are local/generated artifacts and are not required as application source:

```text
.venv/
__pycache__/
.pytest_cache/
input/
output/
web_data/
inspect.txt
```

The `inspect` CLI command itself remains available as a development utility.
