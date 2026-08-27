from __future__ import annotations

import argparse

from .core import inspect_xliff
from .nllb import NLLBTranslator
from .pipeline import translate_file


NLLB_LANGUAGES = {
    "en": "eng_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
}


def cmd_inspect(
    args,
):
    lines = inspect_xliff(
        args.input
    )

    for line in lines:
        print(line)


def cmd_translate(
    args,
):
    print(
        f"Loading NLLB model: "
        f"{args.model}"
    )

    translator = NLLBTranslator(
        model_name=args.model,
        batch_size=args.batch_size,
    )

    target_languages = [
        NLLB_LANGUAGES.get(
            language.lower(),
            language,
        )
        for language in args.langs
    ]

    outputs = translate_file(
        input_path=args.input,
        output_dir=args.output_dir,
        languages=target_languages,
        translator=translator,
    )

    print()
    print(
        "Translation complete."
    )

    for output in outputs:
        print(
            f"  {output}"
        )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="xliff_translator",
        description=(
            "Structure-preserving XLIFF "
            "translator using NLLB."
        ),
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    # --------------------------------------------------
    # INSPECT
    # --------------------------------------------------

    inspect_parser = (
        subparsers.add_parser(
            "inspect",
            help="Inspect an XLIFF file.",
        )
    )

    inspect_parser.add_argument(
        "input",
        help="Input XLIFF file.",
    )

    inspect_parser.set_defaults(
        func=cmd_inspect
    )

    # --------------------------------------------------
    # TRANSLATE
    # --------------------------------------------------

    translate_parser = (
        subparsers.add_parser(
            "translate",
            help="Translate an XLIFF file.",
        )
    )

    translate_parser.add_argument(
        "input",
        help="Input XLIFF file.",
    )

    translate_parser.add_argument(
        "--langs",
        nargs="+",
        required=True,
        help=(
            "Target languages. "
            "Examples: fr de"
        ),
    )

    translate_parser.add_argument(
        "--model",
        default=(
            "facebook/"
            "nllb-200-distilled-600M"
        ),
        help="NLLB model name.",
    )

    translate_parser.add_argument(
        "--output-dir",
        default="./output",
        help=(
            "Directory for translated "
            "XLIFF files."
        ),
    )

    translate_parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help=(
            "Number of text nodes sent to "
            "NLLB at a time. Default: 4."
        ),
    )

    translate_parser.set_defaults(
        func=cmd_translate
    )

    return parser


def main():
    parser = build_parser()

    args = parser.parse_args()

    args.func(args)


if __name__ == "__main__":
    main()