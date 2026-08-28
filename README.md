# XLIFF NLLB Translator

A local Python tool for translating XLIFF 1.2 files with NLLB while preserving the original XML structure, IDs, attributes, inline `<g>` elements, and non-translatable XML content.

## Design

The original `<source>` is never modified. For each `<trans-unit>`, the tool creates/replaces a `<target>` containing the translated text while cloning the source structure.

For structured sources, text leaves are extracted into numbered protected segments. NLLB translates the combined text with protected markers. The translated text is mapped back onto the exact original text-node positions, so formatting nodes and attributes remain untouched.

Empty/markup-only units are copied without translation.

## Install

Python 3.10+ is recommended.

```powershell
cd xliff_translator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For CPU use the default PyTorch install. For NVIDIA GPU, install the appropriate CUDA-enabled PyTorch build first, then install the requirements.

## Usage

Dry-run extraction (no model required):

```powershell
python -m xliff_translator inspect input.xlf
```

Translate to French and German:

```powershell
python -m xliff_translator translate input.xlf --langs fr,de --output-dir output
```

Specify the NLLB model explicitly:

```powershell
python -m xliff_translator translate input.xlf --langs fr,de --model facebook/nllb-200-distilled-600M --output-dir output
```

GPU:

```powershell
python -m xliff_translator translate input.xlf --langs fr,de --device cuda --output-dir output
```

Use a larger model if GPU memory allows:

```powershell
--model facebook/nllb-200-1.3B
```

## Important

NLLB language codes used by this project are `eng_Latn`, `fra_Latn`, and `deu_Latn`.

The implementation deliberately does not pretty-print XML. It preserves the XML tree and only inserts/replaces `<target>` elements. XML serialization can still normalize insignificant byte-level formatting; semantic structure, element names, attributes, IDs and ordering are preserved.


### Progress bar

The `translate` command shows a per-language progress bar as each `trans-unit` is processed. The progress bar starts after NLLB finishes loading; model download/loading can still take time before translation begins.
