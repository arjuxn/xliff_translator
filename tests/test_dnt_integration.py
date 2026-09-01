from __future__ import annotations

from pathlib import Path

from xliff_translator.dnt import (
    count_dnt_terms,
    find_dnt_terms_in_text,
    validate_dnt_preservation,
)
from xliff_translator.pipeline import (
    translate_file,
)


class FakeTranslator:
    """
    Fake translation engine for pipeline-level tests.

    It simulates a translator that changes ordinary text
    while leaving DNT terms unchanged.

    This test deliberately does not load NLLB, so the test
    suite remains fast and does not require a model download.
    """

    batch_size = 4

    def translate_batch(
        self,
        texts,
        source_lang,
        target_lang,
        protected_terms=None,
    ):

        outputs = []

        for index, text in enumerate(
            texts
        ):

            if protected_terms is None:
                terms = []

            else:
                terms = protected_terms[
                    index
                ]

            output = text

            # Simulate translation of normal English
            # words while preserving DNT terms.
            replacements = {
                "Use": "Utilisez",
                "uses": "utilise",
                "and": "et",
                "the": "le",
                "This": "Cette",
                "lesson": "leçon",
            }

            for source, target in (
                replacements.items()
            ):

                output = output.replace(
                    source,
                    target,
                )

            # Explicitly restore DNT terms in this fake
            # translator to model the expected behaviour.
            #
            # The real NLLB implementation achieves this
            # using constrained beam search.
            if terms:

                # Nothing needs to be done here because
                # the fake replacement table does not touch
                # the protected terms.

                pass

            outputs.append(
                output
            )

        return outputs


def make_fixture(
    tmp_path: Path,
) -> Path:

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file source-language="en" datatype="x-undefined" original="test">
    <body>
      <trans-unit id="1">
        <source>Use CATIA and ENOVIA.</source>
      </trans-unit>
      <trans-unit id="2">
        <source>This lesson uses 3DEXPERIENCE.</source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

    path = (
        tmp_path / "fixture.xlf"
    )

    path.write_text(
        xml,
        encoding="utf-8",
    )

    return path


def test_pipeline_preserves_dnt_terms(
    tmp_path: Path,
):

    input_path = make_fixture(
        tmp_path
    )

    dnt_path = (
        tmp_path / "dnt.txt"
    )

    dnt_path.write_text(
        "\n".join(
            [
                "CATIA",
                "ENOVIA",
                "3DEXPERIENCE",
            ]
        ),
        encoding="utf-8",
    )

    output_dir = (
        tmp_path / "output"
    )

    translator = FakeTranslator()

    outputs = translate_file(
        input_path=input_path,
        output_dir=output_dir,
        languages=["fra_Latn"],
        translator=translator,
        dnt_path=dnt_path,
    )

    assert len(outputs) == 1

    output_text = outputs[
        0
    ].read_text(
        encoding="utf-8"
    )

    assert "CATIA" in output_text
    assert "ENOVIA" in output_text
    assert "3DEXPERIENCE" in output_text


def test_dnt_occurrence_counts_are_preserved():

    source = (
        "CATIA connects CATIA to ENOVIA."
    )

    translated = (
        "CATIA relie CATIA à ENOVIA."
    )

    validate_dnt_preservation(
        source,
        translated,
        [
            "CATIA",
            "ENOVIA",
        ],
    )

    assert count_dnt_terms(
        source,
        [
            "CATIA",
            "ENOVIA",
        ],
    ) == {
        "CATIA": 2,
        "ENOVIA": 1,
    }


def test_dnt_terms_are_detected_per_text():

    terms = [
        "CATIA",
        "ENOVIA",
        "3DEXPERIENCE",
    ]

    text_a = (
        "Use CATIA and ENOVIA."
    )

    text_b = (
        "Use 3DEXPERIENCE."
    )

    assert find_dnt_terms_in_text(
        text_a,
        terms,
    ) == [
        "CATIA",
        "ENOVIA",
    ]

    assert find_dnt_terms_in_text(
        text_b,
        terms,
    ) == [
        "3DEXPERIENCE"
    ]