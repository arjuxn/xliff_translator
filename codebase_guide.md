# XLIFF NLLB Translator — Codebase Guide

This document describes the current implementation and the responsibility of each component.

## 1. Architecture overview

The application is divided into four main backend layers:

```text
                XLIFF file
                    |
                    v
                core.py
          XML parsing/extraction
                    |
                    v
             Translation tasks
                    |
                    v
              pipeline.py
           workflow orchestration
                    |
                    v
                nllb.py
           neural translation
                    |
                    v
           translated text
                    |
                    v
                core.py
          target reconstruction
                    |
                    v
          structural validation
                    |
                    v
             output XLIFF
```

DNT is handled separately:

```text
DNT input
    |
    v
  dnt.py
    |
    v
Find matching terms
    |
    v
  nllb.py
    |
    v
Temporary placeholders
    |
    v
NLLB translation
    |
    v
Restore original terms
    |
    v
Validate DNT preservation
```

The current implementation does not depend on the old `protection.py`, `deprotection.py`, or `segments.py` architecture.

## 2. Directory structure

```text
xliff_translator/
├── README.md
├── CODEBASE_GUIDE.md
├── pyproject.toml
├── requirements.txt
├── tests/
│   ├── fixture.xlf
│   ├── test_dnt.py
│   ├── test_reconstruction.py
│   └── other tests
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

## 3. core.py

`core.py` contains the low-level XLIFF/XML functionality.

Responsibilities:

- Parse XLIFF files.
- Find `trans-unit`, `source`, and `target` elements.
- Identify text locations.
- Create translation tasks.
- Deep-copy source structures.
- Apply translated text to copied structures.
- Add or replace target elements.
- Validate structural integrity.
- Write translated XLIFF files.
- Provide the `inspect` development utility.

XML text can occur in both:

```text
element.text
element.tail
```

The application tracks these locations so translated strings can be returned to the correct structural positions.

## 4. Translation tasks

A translation task associates text with its original location:

```text
TranslationTask
├── unit_index
├── location_index
└── text
```

This mapping prevents translated text from being inserted into the wrong XML location.

## 5. XML preservation strategy

The original source is never modified.

```text
Original XLIFF
     |
     +----------------------+
     |                      |
     v                      v
Original tree          Working tree
     |                      |
     |                      v
     |                Clone source
     v                      |
Extract text                |
     |                      |
     v                      |
Translate text              |
     |                      |
     +----------+-----------+
                |
                v
       Insert translated text
                |
                v
        Validate structure
                |
                v
           Write output
```

The working target is based on a deep copy of the source structure.

This preserves:

- element hierarchy
- element names
- attributes
- IDs
- inline XML elements
- ordering

Only textual values are replaced.

## 6. dnt.py

`dnt.py` implements Do Not Translate functionality.

Responsibilities:

- Load DNT terms from text files.
- Normalize DNT terms.
- Find DNT terms in source text.
- Identify matching spans.
- Count matches.
- Validate final DNT preservation.

DNT terms can be words or phrases.

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

A protected term is temporarily replaced by a synthetic placeholder before NLLB translation.

After translation, the placeholder is recognized and replaced with the original DNT term.

The original term is restored exactly.

If the protected term cannot be reliably restored, translation fails.

## 7. nllb.py

`nllb.py` provides the NLLB inference engine.

The main class is:

```text
NLLBTranslator
```

Responsibilities:

- Select CPU or CUDA.
- Load the tokenizer.
- Load the NLLB model.
- Configure model precision.
- Tokenize batches.
- Generate translations.
- Decode generated tokens.
- Handle DNT placeholders.
- Restore DNT terms.
- Validate DNT preservation.

Default model:

```text
facebook/nllb-200-distilled-600M
```

When `device="auto"`, CUDA is selected when available; otherwise CPU is used.

## 8. DNT placeholder behavior

NLLB is a translation model, so DNT terms are temporarily replaced before translation.

Example:

```text
Original:
Congratulations! You have completed this lesson.

Protected:
XliffProtectedTermZero You have completed this lesson.
```

NLLB may insert whitespace inside the synthetic placeholder:

```text
Xliff ProtectedTermZero
```

The restoration logic accounts for whitespace changes inside the placeholder.

The original term is then restored:

```text
Congratulations! Vous avez terminé cette leçon.
```

The final result is validated to ensure the DNT term remains present.

## 9. pipeline.py

`pipeline.py` is the orchestration layer.

It coordinates:

1. Loading the input XLIFF.
2. Loading DNT terms.
3. Creating translation tasks.
4. Sending batches to NLLB.
5. Mapping translations back to XML locations.
6. Rebuilding target structures.
7. Validating translated XML.
8. Writing output files.

Conceptually:

```text
translate_file()
       |
       +--> load DNT terms
       |
       +--> parse original tree
       |
       +--> parse working tree
       |
       +--> build translation tasks
       |
       +--> translate tasks
       |
       +--> rebuild targets
       |
       +--> validate translation tree
       |
       +--> write output
```

The pipeline delegates low-level XML operations to `core.py` and neural inference/DNT protection to `nllb.py`.

## 10. cli.py

`cli.py` provides the command-line interface.

Current commands:

```text
inspect
translate
```

Responsibilities:

- Parse command-line arguments.
- Map short language codes to NLLB language codes.
- Configure the translator.
- Invoke the pipeline.
- Report errors and progress.

## 11. __main__.py

Provides module execution support:

```powershell
python -m xliff_translator
```

It dispatches to the CLI.

## 12. Web application

The web application is under:

```text
xliff_translator/web/
```

### app.py

FastAPI application responsible for:

- Serving the GUI.
- Receiving XLIFF uploads.
- Receiving language selections.
- Receiving model settings.
- Receiving DNT terms.
- Receiving optional DNT files.
- Starting translations.
- Saving output files.
- Providing download endpoints.
- Returning API responses.

Current endpoints include:

```text
GET  /
GET  /api/health
POST /api/translate
GET  /api/download/{job_id}/{filename}
```

### static/index.html

Defines the GUI structure for:

- XLIFF upload
- target language selection
- model selection
- DNT term entry
- optional DNT file upload
- translation status
- output downloads

### static/app.js

Handles:

- File selection
- Drag and drop
- DNT term input
- DNT file selection
- Form submission
- Loading state
- API requests
- Success handling
- Error handling
- Download links

### static/style.css

Contains frontend styling.

## 13. Validation

Before output is written, the translated XML tree is validated against the original tree.

Validation is intended to catch:

- changed trans-unit count
- changed IDs
- changed source structures
- changed element hierarchy
- changed attributes
- unexpected structural differences

The application should not report a successful output when structural validation fails.

## 14. CLI inspect utility

The `inspect` command is a development utility for examining an XLIFF without loading NLLB.

Example:

```powershell
python -m xliff_translator inspect input.xlf
```

It can show:

- translation-unit IDs
- source content
- text locations
- `.text` and `.tail` values

`inspect.txt` is not required by the application. It is only a possible saved output/scratch file.

## 15. Testing

Run all tests:

```powershell
python -m pytest -q
```

The test suite covers the implemented behavior, including:

- DNT loading and normalization
- DNT matching
- DNT preservation
- DNT restoration
- translation-task mapping
- XML reconstruction
- source immutability
- structural validation
- IDs and attributes
- inline XML structures

## 16. Removed architecture

The following modules belonged to an earlier design:

```text
protection.py
deprotection.py
segments.py
```

They are not part of the current translation flow.

The current implementation uses:

```text
core.py
dnt.py
nllb.py
pipeline.py
```

for XML handling, DNT handling, inference, and orchestration.

## 17. Packaging

`pyproject.toml` defines the Python package and CLI entry point.

The CLI entry point is:

```text
xliff-translator
```

and maps to:

```text
xliff_translator.cli:main
```

Runtime dependencies are declared in the project configuration and requirements file.

## 18. Runtime artifacts

The following are local or generated artifacts:

```text
.venv/
__pycache__/
.pytest_cache/
input/
output/
web_data/
inspect.txt
```

They do not need to be included when distributing the application source.

## 19. Design principles

### Separate XML processing from translation

NLLB operates on text while XML structure is managed separately.

### Never mutate the original source

The source tree is retained as the structural reference.

### Preserve structure

Targets are built from copies of source structures.

### Protect explicit DNT terms

Terms explicitly supplied as DNT must remain unchanged.

### Fail safely

If DNT preservation or structural validation fails, the application reports an error instead of silently producing an invalid result.

### Keep responsibilities separated

XML processing, DNT handling, neural inference, orchestration, and the web interface have separate responsibilities.
