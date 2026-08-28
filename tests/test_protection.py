from lxml import etree

from xliff_translator.protection import (
    protect_source,
    validate_markers,
)


XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"


def make_source(xml: str) -> etree._Element:
    return etree.fromstring(
        xml.encode("utf-8")
    )


def test_plain_text_is_preserved():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Hello world
        </source>
        """
    )

    result = protect_source(source)

    assert "Hello world" in result.text
    assert result.markers == {}


def test_single_g_element_is_protected():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Click
            <g id="g1">START</g>
            to begin.
        </source>
        """
    )

    result = protect_source(source)

    assert "[[XLIFF_G_g1_0_START]]" in result.text
    assert "[[XLIFF_G_g1_0_END]]" in result.text
    assert "START" in result.text

    assert len(result.markers) == 1
    assert result.markers["XLIFF_G_g1_0"].get("id") == "g1"


def test_nested_g_elements_are_protected():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            <g id="outer">
                Hello
                <g id="inner">world</g>
            </g>
        </source>
        """
    )

    result = protect_source(source)

    assert len(result.markers) == 2

    assert "[[XLIFF_G_outer_0_START]]" in result.text
    assert "[[XLIFF_G_outer_0_END]]" in result.text

    assert "[[XLIFF_G_inner_1_START]]" in result.text
    assert "[[XLIFF_G_inner_1_END]]" in result.text

    assert "Hello" in result.text
    assert "world" in result.text


def test_tail_text_is_preserved():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Before
            <g id="g1">inside</g>
            After
        </source>
        """
    )

    result = protect_source(source)

    assert "Before" in result.text
    assert "inside" in result.text
    assert "After" in result.text


def test_marker_validation_accepts_unchanged_markers():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Hello <g id="g1">world</g>
        </source>
        """
    )

    result = protect_source(source)

    validate_markers(result.text, result)


def test_marker_validation_rejects_missing_marker():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Hello <g id="g1">world</g>
        </source>
        """
    )

    result = protect_source(source)

    bad_translation = "Bonjour world"

    try:
        validate_markers(bad_translation, result)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for missing XLIFF markers"
        )