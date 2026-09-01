from pathlib import Path

import pytest

from xliff_translator.dnt import (
    count_dnt_terms,
    find_dnt_spans,
    find_dnt_terms_in_text,
    load_dnt_terms,
    normalise_dnt_terms,
    protect_dnt_terms,
    restore_dnt_terms,
    validate_dnt_preservation,
)


def test_dnt_terms_are_loaded(
    tmp_path: Path,
):

    dnt_file = (
        tmp_path / "terms.txt"
    )

    dnt_file.write_text(
        """
CATIA
3DEXPERIENCE
ENOVIA
""",
        encoding="utf-8",
    )

    terms = load_dnt_terms(
        dnt_file
    )

    assert terms == [
        "CATIA",
        "3DEXPERIENCE",
        "ENOVIA",
    ]


def test_utf8_bom_is_supported(
    tmp_path: Path,
):

    dnt_file = (
        tmp_path / "terms.txt"
    )

    dnt_file.write_text(
        "CATIA\nENOVIA\n",
        encoding="utf-8-sig",
    )

    terms = load_dnt_terms(
        dnt_file
    )

    assert terms == [
        "CATIA",
        "ENOVIA",
    ]


def test_blank_dnt_lines_are_ignored():

    terms = normalise_dnt_terms(
        [
            "",
            "   ",
            "CATIA",
            "",
            "ENOVIA",
        ]
    )

    assert terms == [
        "CATIA",
        "ENOVIA",
    ]


def test_duplicate_terms_are_removed():

    terms = normalise_dnt_terms(
        [
            "CATIA",
            "ENOVIA",
            "CATIA",
        ]
    )

    assert terms == [
        "CATIA",
        "ENOVIA",
    ]


def test_dnt_is_case_sensitive():

    text = (
        "CATIA catia CATIA."
    )

    spans = find_dnt_spans(
        text,
        ["CATIA"],
    )

    assert [
        term
        for _, _, term in spans
    ] == [
        "CATIA",
        "CATIA",
    ]


def test_dnt_does_not_match_inside_words():

    text = (
        "CATIAX uses CATIA."
    )

    matches = find_dnt_terms_in_text(
        text,
        ["CATIA"],
    )

    assert matches == [
        "CATIA"
    ]


def test_longer_terms_take_precedence():

    text = (
        "CATIA V6"
    )

    spans = find_dnt_spans(
        text,
        [
            "CATIA",
            "CATIA V6",
        ],
    )

    assert spans == [
        (
            0,
            8,
            "CATIA V6",
        )
    ]


def test_multiple_occurrences():

    text = (
        "CATIA and CATIA are products."
    )

    matches = find_dnt_terms_in_text(
        text,
        ["CATIA"],
    )

    assert matches == [
        "CATIA",
        "CATIA",
    ]


def test_count_dnt_terms():

    text = (
        "CATIA uses ENOVIA. "
        "CATIA connects to ENOVIA."
    )

    counts = count_dnt_terms(
        text,
        [
            "CATIA",
            "ENOVIA",
        ],
    )

    assert counts == {
        "CATIA": 2,
        "ENOVIA": 2,
    }


def test_dnt_at_start_and_end():

    text = (
        "CATIA is powerful"
    )

    matches = find_dnt_terms_in_text(
        text,
        ["CATIA"],
    )

    assert matches == [
        "CATIA"
    ]


def test_dnt_next_to_punctuation():

    text = (
        "(CATIA), [ENOVIA]."
    )

    matches = find_dnt_terms_in_text(
        text,
        [
            "CATIA",
            "ENOVIA",
        ],
    )

    assert matches == [
        "CATIA",
        "ENOVIA",
    ]


def test_dnt_with_spaces():

    text = (
        "Use 3DEXPERIENCE Platform now."
    )

    matches = find_dnt_terms_in_text(
        text,
        ["3DEXPERIENCE Platform"],
    )

    assert matches == [
        "3DEXPERIENCE Platform"
    ]


def test_dnt_preservation_accepts_exact_output():

    source = (
        "Use CATIA and ENOVIA."
    )

    translated = (
        "Utilisez CATIA et ENOVIA."
    )

    validate_dnt_preservation(
        source,
        translated,
        [
            "CATIA",
            "ENOVIA",
        ],
    )


def test_dnt_preservation_rejects_translated_term():

    source = (
        "Use CATIA."
    )

    translated = (
        "Utilisez KATIA."
    )

    with pytest.raises(
        ValueError,
        match="CATIA",
    ):

        validate_dnt_preservation(
            source,
            translated,
            ["CATIA"],
        )


def test_dnt_preservation_rejects_missing_occurrence():

    source = (
        "CATIA and CATIA."
    )

    translated = (
        "CATIA und."
    )

    with pytest.raises(
        ValueError,
        match="CATIA",
    ):

        validate_dnt_preservation(
            source,
            translated,
            ["CATIA"],
        )


def test_dnt_preservation_rejects_extra_occurrence():

    source = (
        "Use CATIA."
    )

    translated = (
        "Utilisez CATIA CATIA."
    )

    with pytest.raises(
        ValueError,
        match="CATIA",
    ):

        validate_dnt_preservation(
            source,
            translated,
            ["CATIA"],
        )


def test_empty_dnt_list_does_nothing():

    source = (
        "This is ordinary text."
    )

    translated = (
        "Ceci est un texte normal."
    )

    validate_dnt_preservation(
        source,
        translated,
        [],
    )


def test_legacy_helpers_still_work():

    source = (
        "Use CATIA and ENOVIA."
    )

    protected, mapping = (
        protect_dnt_terms(
            source,
            [
                "CATIA",
                "ENOVIA",
            ],
        )
    )

    restored = restore_dnt_terms(
        protected,
        mapping,
    )

    assert restored == source