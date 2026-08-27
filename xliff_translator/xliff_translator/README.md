# XLIFF NLLB Translator — structure-safe POC

This version changes the core design so the XML tree belongs to the program, not to NLLB.

For every `<trans-unit>`:

1. Parse the XLIFF into an XML tree with `lxml`.
2. Keep the original `<source>` tree untouched.
3. Find textual leaves (`element.text` and `child.tail`) in document order.
4. Send the unit's text to NLLB with protected segment markers when there are multiple text leaves.
5. Validate that every marker survived exactly twice.
6. Clone the original `<source>` into `<target>`.
7. Replace only the text leaves in that clone.
8. Run a structural validator before writing the file.
9. If NLLB drops inline markers, the default `leaf` fallback translates each text leaf separately. This preserves XML structure at the cost of some linguistic context. Use `--fallback error` if you prefer a hard failure instead.

The output is therefore never reconstructed by asking NLLB to generate XML.

## Install

```powershell
cd xliff_translator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For an NVIDIA GPU, install a CUDA-enabled PyTorch build appropriate for your machine before installing the remaining requirements.

## Inspect without loading NLLB

```powershell
python -m xliff_translator inspect Create-functional-architecture.xlf
```

This shows the 56 translation units and the text leaves found inside each source tree.

## Translate

French:

```powershell
python -m xliff_translator translate Create-functional-architecture.xlf --langs fr --model facebook/nllb-200-distilled-600M --output-dir ./output
```

French + German:

```powershell
python -m xliff_translator translate Create-functional-architecture.xlf --langs fr de --model facebook/nllb-200-distilled-600M --output-dir ./output
```

Fail instead of using the safe per-leaf fallback:

```powershell
python -m xliff_translator translate Create-functional-architecture.xlf --langs fr --fallback error
```

## What is guaranteed by the reconstruction layer

Before an output XLIFF is written, it checks:

- same number of `<trans-unit>` elements
- same trans-unit IDs and order
- original `<source>` elements and their text are unchanged
- target exists for every unit
- target has the same element hierarchy and attributes as the source
- inline `<g>` elements and their attributes are copied from source
- empty/markup-only sources remain empty
- requested `target-language` is set on each `<file>`

This is semantic XML preservation. XML serialization may change insignificant byte-level formatting such as indentation.

## Important limitation

A neural translation model is not guaranteed to preserve protected markers. The protected whole-unit path gives better context, but it can fail. The safe fallback translates individual text leaves so the XML structure remains exact. For production quality, the next step is to add a stronger alignment/segmentation strategy and terminology protection rather than silently accepting malformed markup.
