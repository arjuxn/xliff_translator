from lxml import etree

from xliff_translator.protection import protect_source
from xliff_translator.deprotection import reconstruct_target


XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"


def make_source(xml: str) -> etree._Element:
    return etree.fromstring(
        xml.encode("utf-8")
    )


def test_plain_text_reconstruction():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Hello world
        </source>
        """
    )

    protected = protect_source(source)

    target = reconstruct_target(
        source,
        "Bonjour monde",
        protected,
    )

    assert target.text.strip() == "Bonjour monde"


def test_single_g_is_reconstructed():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Click <g id="g1">START</g> to begin.
        </source>
        """
    )

    protected = protect_source(source)

    translated = (
        "Cliquez "
        "[[XLIFF_G_g1_0_START]]DÉMARRER"
        "[[XLIFF_G_g1_0_END]] "
        "pour commencer."
    )

    target = reconstruct_target(
        source,
        translated,
        protected,
    )

    g = target[0]

    assert g.tag == f"{{{XLIFF_NS}}}g"
    assert g.get("id") == "g1"
    assert g.text == "DÉMARRER"

    assert "Cliquez" in target.text
    assert "pour commencer." in g.tail


def test_nested_g_elements_are_reconstructed():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            <g id="outer">
                Hello
                <g id="inner">
                    world
                </g>
                !
            </g>
        </source>
        """
    )

    protected = protect_source(source)

    translated = (
        "[[XLIFF_G_outer_0_START]]"
        "Bonjour "
        "[[XLIFF_G_inner_1_START]]"
        "monde"
        "[[XLIFF_G_inner_1_END]]"
        " !"
        "[[XLIFF_G_outer_0_END]]"
    )

    target = reconstruct_target(
        source,
        translated,
        protected,
    )

    outer = target[0]
    inner = outer[0]

    assert outer.tag == f"{{{XLIFF_NS}}}g"
    assert outer.get("id") == "outer"

    assert inner.tag == f"{{{XLIFF_NS}}}g"
    assert inner.get("id") == "inner"

    assert inner.text == "monde"

    assert outer.text == "Bonjour "
    assert inner.tail == " !"


def test_original_attributes_are_preserved():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Hello
            <g
                id="g1"
                ctype="x-html-B"
                equiv-text="START"
            >
                START
            </g>
        </source>
        """
    )

    protected = protect_source(source)

    translated = (
        "Bonjour "
        "[[XLIFF_G_g1_0_START]]DÉMARRER"
        "[[XLIFF_G_g1_0_END]]"
    )

    target = reconstruct_target(
        source,
        translated,
        protected,
    )

    g = target[0]

    assert g.get("id") == "g1"
    assert g.get("ctype") == "x-html-B"
    assert g.get("equiv-text") == "START"


def test_source_is_not_modified():

    source = make_source(
        f"""
        <source xmlns="{XLIFF_NS}">
            Hello <g id="g1">world</g>
        </source>
        """
    )

    original_xml = etree.tostring(
        source,
        encoding="utf-8",
    )

    protected = protect_source(source)

    translated = (
        "Bonjour "
        "[[XLIFF_G_g1_0_START]]monde"
        "[[XLIFF_G_g1_0_END]]"
    )

    reconstruct_target(
        source,
        translated,
        protected,
    )

    assert etree.tostring(
        source,
        encoding="utf-8",
    ) == original_xml