from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


XLIFF_NAMESPACE = "urn:oasis:names:tc:xliff:document:1.2"


@dataclass
class TranslationTask:
    """
    One text location that should be sent to the translator.

    unit_index:
        Position of the trans-unit in the XLIFF document.

    location_index:
        Position of the text location inside that trans-unit's source.

    text:
        Actual text sent to NLLB.
    """

    unit_index: int
    location_index: int
    text: str


def parse_xliff(
    path: str | Path,
) -> etree._ElementTree:
    """
    Parse an XLIFF file while preserving XML structure.

    Blank text, comments, CDATA, and processing instructions are
    intentionally preserved.
    """

    parser = etree.XMLParser(
        remove_blank_text=False,
        resolve_entities=False,
        strip_cdata=False,
        remove_comments=False,
    )

    return etree.parse(
        str(path),
        parser,
    )


def find_trans_units(
    tree: etree._ElementTree,
) -> list[etree._Element]:
    """
    Return every <trans-unit> in document order.
    """

    return tree.xpath(
        "//*[local-name()='trans-unit']"
    )


def get_unit_id(
    trans_unit: etree._Element,
) -> str:
    """
    Return the ID of a trans-unit.
    """

    return trans_unit.get(
        "id",
        "",
    )


def find_source(
    trans_unit: etree._Element,
) -> etree._Element | None:
    """
    Find the <source> element directly inside a trans-unit.
    """

    for child in trans_unit:
        if etree.QName(child).localname == "source":
            return child

    return None


def find_target(
    trans_unit: etree._Element,
) -> etree._Element | None:
    """
    Find the <target> element directly inside a trans-unit.
    """

    for child in trans_unit:
        if etree.QName(child).localname == "target":
            return child

    return None


def replace_or_add_target(
    trans_unit: etree._Element,
    target_content: etree._Element,
) -> etree._Element:
    """
    Replace an existing <target>, or create a new <target>.

    target_content is already a reconstructed target element.

    The original <source> is never modified.
    """

    old_target = find_target(
        trans_unit
    )

    if old_target is not None:
        index = trans_unit.index(
            old_target
        )

        target = etree.Element(
            old_target.tag,
            attrib=dict(
                old_target.attrib
            ),
            nsmap=old_target.nsmap,
        )

        target.text = target_content.text

        for child in target_content:
            target.append(
                deepcopy(child)
            )

        trans_unit.remove(
            old_target
        )

        trans_unit.insert(
            index,
            target,
        )

        return target

    source = find_source(
        trans_unit
    )

    if source is None:
        raise ValueError(
            f"trans-unit {get_unit_id(trans_unit)} "
            "has no source."
        )

    if source.tag.startswith("{"):
        namespace = (
            source.tag.split(
                "}",
                1,
            )[0]
            + "}"
        )

        target_tag = (
            f"{namespace}target"
        )
    else:
        target_tag = "target"

    target = etree.Element(
        target_tag,
        nsmap=source.nsmap,
    )

    target.text = target_content.text

    for child in target_content:
        target.append(
            deepcopy(child)
        )

    source_index = trans_unit.index(
        source
    )

    trans_unit.insert(
        source_index + 1,
        target,
    )

    return target


def inspect_xliff(
    path: str | Path,
) -> list[str]:
    """
    Produce a human-readable inspection of an XLIFF file.
    """

    tree = parse_xliff(
        path
    )

    units = find_trans_units(
        tree
    )

    lines: list[str] = []

    lines.append(
        f"XLIFF: {Path(path).name}"
    )

    lines.append(
        f"trans-units: {len(units)}"
    )

    lines.append("")

    for index, unit in enumerate(
        units
    ):
        lines.append(
            f"[{index}] id={get_unit_id(unit)}"
        )

        source = find_source(
            unit
        )

        if source is None:
            lines.append(
                "  source: MISSING"
            )

            lines.append("")
            continue

        locations = iter_text_locations(
            source
        )

        if not locations:
            lines.append(
                "  (markup-only / empty)"
            )

            lines.append("")
            continue

        for leaf_index, location in enumerate(
            locations
        ):
            text = location.text

            if text is None:
                text = ""

            text = text.replace(
                "\n",
                "\\n",
            )

            lines.append(
                f"  leaf {leaf_index}: {text!r}"
            )

        lines.append("")

    return lines


class TextLocation:
    """
    Points to exactly one text location in an XML tree.

    The text can be either:

        element.text

    or:

        child.tail
    """

    def __init__(
        self,
        element: etree._Element,
        attribute: str,
    ):
        self.element = element
        self.attribute = attribute

    @property
    def text(
        self,
    ) -> str | None:
        return getattr(
            self.element,
            self.attribute,
        )

    @text.setter
    def text(
        self,
        value: str,
    ):
        setattr(
            self.element,
            self.attribute,
            value,
        )


def iter_text_locations(
    element: etree._Element,
) -> list[TextLocation]:
    """
    Walk an XML subtree and return every text location.

    XML text can exist in two important places:

        <g>Hello</g>
            ^ element.text

    and:

        <g>Hello</g> world
                     ^ child.tail

    Both are collected.

    Nested elements are recursively traversed.
    """

    locations: list[TextLocation] = []

    def walk(
        node: etree._Element,
    ):
        if node.text:
            locations.append(
                TextLocation(
                    element=node,
                    attribute="text",
                )
            )

        for child in node:
            walk(
                child
            )

            if child.tail:
                locations.append(
                    TextLocation(
                        element=child,
                        attribute="tail",
                    )
                )

    walk(
        element
    )

    return locations


def build_translation_tasks(
    tree: etree._ElementTree,
) -> list[TranslationTask]:
    """
    Create translation tasks from all source text locations.

    Only actual text nodes are returned.

    XML elements themselves are never sent to NLLB.
    """

    tasks: list[TranslationTask] = []

    units = find_trans_units(
        tree
    )

    for unit_index, unit in enumerate(
        units
    ):
        source = find_source(
            unit
        )

        if source is None:
            continue

        locations = iter_text_locations(
            source
        )

        for location_index, location in enumerate(
            locations
        ):
            text = location.text

            if text is None:
                text = ""

            tasks.append(
                TranslationTask(
                    unit_index=unit_index,
                    location_index=location_index,
                    text=text,
                )
            )

    return tasks


def clone_source(
    source: etree._Element,
) -> etree._Element:
    """
    Make a completely independent copy of <source>.

    The clone becomes <target>.

    All nested elements and attributes are preserved.
    """

    cloned = deepcopy(
        source
    )

    if cloned.tag.startswith("{"):
        namespace = (
            cloned.tag.split(
                "}",
                1,
            )[0]
            + "}"
        )

        cloned.tag = (
            f"{namespace}target"
        )

    else:
        cloned.tag = "target"

    return cloned


def apply_leaf_translations(
    target: etree._Element,
    source: etree._Element,
    translated_segments: list[str],
) -> None:
    """
    Replace text locations in target with translated
    segments.

    The XML structure is never reconstructed here.

    Only .text and .tail values are changed.
    """

    source_locations = iter_text_locations(
        source
    )

    target_locations = iter_text_locations(
        target
    )

    if len(source_locations) != len(
        target_locations
    ):
        raise ValueError(
            "Source and target have different "
            "numbers of text locations."
        )

    if len(translated_segments) != len(
        target_locations
    ):
        raise ValueError(
            "Number of translated segments does "
            "not match number of text locations."
        )

    for location, translation in zip(
        target_locations,
        translated_segments,
    ):
        location.text = translation


def build_translation_target(
    source: etree._Element,
    translated_segments: list[str],
) -> etree._Element:
    """
    Build a translated <target> from a <source>.

    The source is deep-copied first.

    The copy is renamed from <source> to <target>.

    Only text locations are replaced.

    All XML structure, nested elements, attributes,
    namespaces, and inline elements are preserved.
    """

    target = clone_source(
        source
    )

    apply_leaf_translations(
        target=target,
        source=source,
        translated_segments=translated_segments,
    )

    return target


def validate_translation_tree(
    original_tree: etree._ElementTree,
    translated_tree: etree._ElementTree,
) -> None:
    """
    Validate that the translated XLIFF retains
    the same trans-unit structure.

    The source must remain structurally identical.
    """

    original_units = find_trans_units(
        original_tree
    )

    translated_units = find_trans_units(
        translated_tree
    )

    if len(original_units) != len(
        translated_units
    ):
        raise ValueError(
            "Translated XLIFF has a different "
            "number of trans-units."
        )

    for original_unit, translated_unit in zip(
        original_units,
        translated_units,
    ):
        original_id = get_unit_id(
            original_unit
        )

        translated_id = get_unit_id(
            translated_unit
        )

        if original_id != translated_id:
            raise ValueError(
                "trans-unit IDs changed: "
                f"{original_id!r} -> "
                f"{translated_id!r}"
            )

        original_source = find_source(
            original_unit
        )

        translated_source = find_source(
            translated_unit
        )

        if original_source is None:
            continue

        if translated_source is None:
            raise ValueError(
                f"Missing source in trans-unit "
                f"{original_id!r}"
            )

        original_structure = [
            (
                element.tag,
                dict(element.attrib),
                len(element),
            )
            for element in original_source.iter()
        ]

        translated_structure = [
            (
                element.tag,
                dict(element.attrib),
                len(element),
            )
            for element in translated_source.iter()
        ]

        if original_structure != translated_structure:
            raise ValueError(
                f"Source structure changed in "
                f"trans-unit {original_id!r}"
            )


def write_xliff(
    tree: etree._ElementTree,
    path: str | Path,
) -> None:
    """
    Write an XLIFF tree to disk.
    """

    path = Path(
        path
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tree.write(
        str(path),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
    )