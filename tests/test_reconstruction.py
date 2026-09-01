from pathlib import Path

from lxml import etree

from xliff_translator.core import (
    apply_leaf_translations,
    clone_source,
    find_source,
    find_target,
    find_trans_units,
    get_unit_id,
    iter_text_locations,
    parse_xliff,
    replace_or_add_target,
    validate_translation_tree,
)


BASE_DIR = Path(__file__).resolve().parent.parent

XLIFF_FILE = (
    Path(__file__).resolve().parent
    / "fixture.xlf"
)


def fake_translate(
    text: str,
    index: int,
) -> str:
    """
    Fake translation used only for testing.
    NLLB is not involved.
    """

    return f"TRANSLATED_{index}"


def create_fake_translation_tree():
    """
    Create a translated XLIFF tree.

    The original <source> is never modified.

    A deep copy of <source> becomes <target>.
    Only text locations inside the target are changed.
    """

    original_tree = parse_xliff(
        XLIFF_FILE
    )

    translated_tree = parse_xliff(
        XLIFF_FILE
    )

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    if len(original_units) != len(
        translated_units
    ):
        raise AssertionError(
            "Original and translated trees have "
            "different trans-unit counts."
        )

    global_index = 0

    for original_unit, translated_unit in zip(
        original_units,
        translated_units,
    ):
        original_source = find_source(
            original_unit
        )

        if original_source is None:
            continue

        target = clone_source(
            original_source
        )

        source_locations = (
            iter_text_locations(
                original_source
            )
        )

        fake_translations = []

        for source_location in source_locations:
            fake_translations.append(
                fake_translate(
                    source_location.text or "",
                    global_index,
                )
            )

            global_index += 1

        apply_leaf_translations(
            target=target,
            source=original_source,
            translated_segments=fake_translations,
        )

        replace_or_add_target(
            trans_unit=translated_unit,
            target_content=target,
        )

    return (
        original_tree,
        translated_tree,
    )


def test_trans_unit_count_is_preserved():
    original_tree, translated_tree = (
        create_fake_translation_tree()
    )

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    assert len(original_units) == 56
    assert len(translated_units) == 56


def test_trans_unit_ids_are_preserved():
    original_tree, translated_tree = (
        create_fake_translation_tree()
    )

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    original_ids = [
        get_unit_id(unit)
        for unit in original_units
    ]

    translated_ids = [
        get_unit_id(unit)
        for unit in translated_units
    ]

    assert original_ids == translated_ids


def test_source_is_unchanged():
    """
    The SOURCE in the translated document must
    remain identical to the SOURCE in the original.

    Translation must happen ONLY in TARGET.
    """

    original_tree, translated_tree = (
        create_fake_translation_tree()
    )

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    for original_unit, translated_unit in zip(
        original_units,
        translated_units,
    ):
        original_source = find_source(
            original_unit
        )

        translated_source = find_source(
            translated_unit
        )

        if original_source is None:
            continue

        assert translated_source is not None

        assert etree.tostring(
            original_source,
            encoding="utf-8",
        ) == etree.tostring(
            translated_source,
            encoding="utf-8",
        )


def test_target_exists():
    """
    Every trans-unit containing a source should
    have a target after reconstruction.
    """

    _, translated_tree = (
        create_fake_translation_tree()
    )

    units = find_trans_units(
        translated_tree
    )

    for unit in units:
        source = find_source(unit)

        if source is None:
            continue

        target = find_target(unit)

        assert target is not None


def normalise_structure(
    element: etree._Element,
):
    """
    Return the XML structure while ignoring text.

    <source> and <target> are treated as equivalent
    containers for structural comparison.
    """

    structure = []

    for child in element.iter():
        tag = child.tag

        if isinstance(tag, str):
            try:
                local_name = etree.QName(
                    child
                ).localname
            except ValueError:
                local_name = tag

            if local_name in (
                "source",
                "target",
            ):
                tag = "TEXT_CONTAINER"

        structure.append(
            (
                tag,
                dict(child.attrib),
                len(child),
            )
        )

    return structure


def test_structure_is_preserved():
    """
    SOURCE and TARGET must have the same XML
    structure.

    Text is allowed to differ.
    """

    original_tree, translated_tree = (
        create_fake_translation_tree()
    )

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    for original_unit, translated_unit in zip(
        original_units,
        translated_units,
    ):
        original_source = find_source(
            original_unit
        )

        target = find_target(
            translated_unit
        )

        if original_source is None:
            continue

        assert target is not None

        assert normalise_structure(
            original_source
        ) == normalise_structure(
            target
        )


def test_nested_elements_are_preserved():
    """
    Verify that nested inline elements such as
    <g> survive reconstruction.
    """

    original_tree, translated_tree = (
        create_fake_translation_tree()
    )

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    for original_unit, translated_unit in zip(
        original_units,
        translated_units,
    ):
        original_source = find_source(
            original_unit
        )

        target = find_target(
            translated_unit
        )

        if original_source is None:
            continue

        assert target is not None

        assert normalise_structure(
            original_source
        ) == normalise_structure(
            target
        )


def test_text_was_actually_replaced():
    """
    Confirm that at least one text location
    was actually changed.
    """

    original_tree, translated_tree = (
        create_fake_translation_tree()
    )

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    changed = False

    for original_unit, translated_unit in zip(
        original_units,
        translated_units,
    ):
        original_source = find_source(
            original_unit
        )

        target = find_target(
            translated_unit
        )

        if original_source is None:
            continue

        assert target is not None

        original_locations = (
            iter_text_locations(
                original_source
            )
        )

        target_locations = (
            iter_text_locations(
                target
            )
        )

        for (
            original_location,
            target_location,
        ) in zip(
            original_locations,
            target_locations,
        ):
            if (
                original_location.text
                != target_location.text
            ):
                changed = True
                break

        if changed:
            break

    assert changed


def test_final_tree_structure_is_valid():
    """
    Run the complete structural validator.
    """

    original_tree, translated_tree = (
        create_fake_translation_tree()
    )

    validate_translation_tree(
        original_tree,
        translated_tree,
    )


def test_text_locations_include_nested_elements():
    """
    Verify that text inside nested elements is
    discovered as an independent text location.
    """

    xml = """
    <source>
        Hello
        <g id="1">world</g>
        again
    </source>
    """

    root = etree.fromstring(
        xml.encode("utf-8")
    )

    locations = iter_text_locations(
        root
    )

    assert len(locations) == 3

    assert locations[0].text.strip() == (
        "Hello"
    )

    assert locations[1].text == (
        "world"
    )

    assert locations[2].text.strip() == (
        "again"
    )


def test_text_locations_can_modify_text_and_tail():
    """
    Verify that changing a text node or tail does
    not destroy the surrounding XML structure.
    """

    xml = """
    <source>
        Hello
        <g id="1">world</g>
        again
    </source>
    """

    root = etree.fromstring(
        xml.encode("utf-8")
    )

    locations = iter_text_locations(
        root
    )

    locations[0].text = "Bonjour "

    locations[1].text = "monde"

    locations[2].text = " encore"

    result = etree.tostring(
        root,
        encoding="unicode",
    )

    assert "<g id=\"1\">monde</g>" in result

    assert "Bonjour" in result

    assert "encore" in result


def test_multiple_nested_levels_are_preserved():
    """
    Verify deeper nesting:

        <source>
            A
            <g>
                B
                <g>
                    C
                </g>
                D
            </g>
            E
        </source>
    """

    xml = """
    <source>
        A
        <g id="outer">
            B
            <g id="inner">C</g>
            D
        </g>
        E
    </source>
    """

    root = etree.fromstring(
        xml.encode("utf-8")
    )

    locations = iter_text_locations(
        root
    )

    assert len(locations) == 5

    assert locations[0].text.strip() == "A"
    assert locations[1].text.strip() == "B"
    assert locations[2].text == "C"
    assert locations[3].text.strip() == "D"
    assert locations[4].text.strip() == "E"

    locations[0].text = "AA"
    locations[1].text = "BB"
    locations[2].text = "CC"
    locations[3].text = "DD"
    locations[4].text = "EE"

    outer = root[0]
    inner = outer[0]

    assert outer.tag == "g"
    assert outer.get("id") == "outer"

    assert inner.tag == "g"
    assert inner.get("id") == "inner"

    assert inner.text == "CC"