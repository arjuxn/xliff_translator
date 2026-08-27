from pathlib import Path
from xliff_translator.core import (
    parse_xliff, iter_units, extract_unit, apply_marked_translation,
    clone_source_as_target, _element_signature, qname, XLIFF_NS,
)

FIXTURE = Path(__file__).parent / "fixture.xlf"


def test_extract_has_units():
    tree = parse_xliff(FIXTURE)
    units = list(iter_units(tree))
    assert len(units) == 56
    assert extract_unit(units[0]).leaves[0].value.strip() == "Create Functional Architecture"


def test_nested_unit_extracts_text_in_order():
    tree = parse_xliff(FIXTURE)
    unit = list(iter_units(tree))[1]
    extraction = extract_unit(unit)
    assert [x.value.strip() for x in extraction.leaves] == [
        "Click", "START", "to begin."
    ]


def test_reconstruction_preserves_exact_nested_structure():
    tree = parse_xliff(FIXTURE)
    unit = list(iter_units(tree))[1]
    extraction = extract_unit(unit)
    translated = (
        "⟦XLSEG:0⟧ Cliquez ⟦XLSEG:0⟧\n"
        "⟦XLSEG:1⟧ DÉMARRER ⟦XLSEG:1⟧\n"
        "⟦XLSEG:2⟧ pour commencer. ⟦XLSEG:2⟧"
    )
    target = apply_marked_translation(extraction, translated)
    assert _element_signature(extraction.source) == _element_signature(target, normalize_root=True)
    assert target.tag == qname(XLIFF_NS, "target")



def test_empty_markup_unit_is_safe():
    tree = parse_xliff(FIXTURE)
    unit = list(iter_units(tree))[4]
    extraction = extract_unit(unit)
    assert extraction.leaves == []
