from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


XLIFF_NAMESPACE = "urn:oasis:names:tc:xliff:document:1.2"


@dataclass
class TextLocation:
    """
    Points to one actual text node inside an XML tree.

    XML text can live in two places:

        element.text

    or:

        child.tail
    """

    index: int
    element: etree._Element
    attribute: str

    @property
    def text(self) -> str | None:
        return getattr(
            self.element,
            self.attribute,
        )

    @text.setter
    def text(self, value: str):
        setattr(
            self.element,
            self.attribute,
            value,
        )


@dataclass
class TranslationTask:
    """
    One text node that will be sent to NLLB.

    The XML element itself is never sent to NLLB.
    """

    unit_index: int
    unit_id: str
    location_index: int
    text: str


def parse_xliff(
    path: str | Path,
) -> etree._ElementTree:
    """
    Parse an XLIFF file while preserving XML structure.
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


def write_xliff(
    tree: etree._ElementTree,
    path: str | Path,
) -> None:
    """
    Write the translated XLIFF back to disk.

    XML indentation already present in the tree is preserved
    because pretty_print is disabled.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tree.write(
        str(path),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
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
    Find the direct <source> child.
    """

    for child in trans_unit:
        if (
            isinstance(child.tag, str)
            and etree.QName(child).localname
            == "source"
        ):
            return child

    return None


def find_target(
    trans_unit: etree._Element,
) -> etree._Element | None:
    """
    Find the direct <target> child.
    """

    for child in trans_unit:
        if (
            isinstance(child.tag, str)
            and etree.QName(child).localname
            == "target"
        ):
            return child

    return None


def iter_text_locations(
    element: etree._Element,
) -> list[TextLocation]:
    """
    Find every meaningful text node in document order.

    This captures both:

        element.text

    and:

        child.tail

    Example:

        <source>
            Hello <g>world</g> again
        </source>

    gives:

        source.text -> "Hello "
        g.text      -> "world"
        g.tail      -> " again"

    Whitespace-only formatting nodes are ignored.
    """

    locations: list[TextLocation] = []

    def walk(
        node: etree._Element,
    ) -> None:
        if (
            node.text is not None
            and node.text.strip()
        ):
            locations.append(
                TextLocation(
                    index=len(locations),
                    element=node,
                    attribute="text",
                )
            )

        for child in node:
            walk(child)

            if (
                child.tail is not None
                and child.tail.strip()
            ):
                locations.append(
                    TextLocation(
                        index=len(locations),
                        element=child,
                        attribute="tail",
                    )
                )

    walk(element)

    return locations


def preserve_whitespace(
    translated: str,
    original: str,
) -> str:
    """
    Preserve the original text node's leading and
    trailing whitespace.

    Only the meaningful text is replaced.
    """

    if not original:
        return translated

    leading_length = (
        len(original)
        - len(original.lstrip())
    )

    trailing_start = len(
        original.rstrip()
    )

    leading = original[
        :leading_length
    ]

    trailing = original[
        trailing_start:
    ]

    return (
        leading
        + translated.strip()
        + trailing
    )


def clone_source(
    source: etree._Element,
) -> etree._Element:
    """
    Deep-copy <source> and turn the copy into <target>.

    Every nested element, attribute, text node,
    tail, namespace and child relationship is preserved.
    """

    cloned = deepcopy(source)

    if not isinstance(
        cloned.tag,
        str,
    ):
        raise ValueError(
            "Source element has an invalid XML tag."
        )

    if cloned.tag.startswith("{"):
        namespace = cloned.tag.split(
            "}",
            1,
        )[0] + "}"

        cloned.tag = (
            f"{namespace}target"
        )
    else:
        cloned.tag = "target"

    return cloned


def replace_or_add_target(
    trans_unit: etree._Element,
    target_content: etree._Element,
) -> etree._Element:
    """
    Replace an existing target or create one.

    The supplied target_content is already a deep
    translated clone of source.
    """

    old_target = find_target(
        trans_unit
    )

    if old_target is not None:
        index = trans_unit.index(
            old_target
        )

        target = deepcopy(
            target_content
        )

        # Keep the original target tag/namespace.
        target.tag = old_target.tag

        # Keep the original target attributes.
        target.attrib.clear()

        for key, value in old_target.attrib.items():
            target.set(
                key,
                value,
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
            f"trans-unit "
            f"{get_unit_id(trans_unit)!r} "
            "has no source."
        )

    source_index = trans_unit.index(
        source
    )

    target = deepcopy(
        target_content
    )

    trans_unit.insert(
        source_index + 1,
        target,
    )

    return target


def build_translation_tasks(
    tree: etree._ElementTree,
) -> list[TranslationTask]:
    """
    Extract all meaningful text nodes from all
    trans-units.

    These are the ONLY strings that will be sent
    to NLLB.
    """

    tasks: list[TranslationTask] = []

    units = find_trans_units(tree)

    for unit_index, unit in enumerate(units):
        source = find_source(unit)

        if source is None:
            continue

        unit_id = get_unit_id(unit)

        locations = iter_text_locations(
            source
        )

        for location in locations:
            text = location.text

            if text is None:
                continue

            if not text.strip():
                continue

            tasks.append(
                TranslationTask(
                    unit_index=unit_index,
                    unit_id=unit_id,
                    location_index=location.index,
                    text=text,
                )
            )

    return tasks


def build_translation_target(
    source: etree._Element,
    translated_segments: list[str],
) -> etree._Element:
    """
    Clone source and put translated text into the
    exact same text locations.

    No XML structure is reconstructed from NLLB output.
    """

    target = clone_source(
        source
    )

    source_locations = (
        iter_text_locations(
            source
        )
    )

    target_locations = (
        iter_text_locations(
            target
        )
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
            "Number of translations does not "
            "match number of text locations."
        )

    for (
        source_location,
        target_location,
        translated,
    ) in zip(
        source_locations,
        target_locations,
        translated_segments,
    ):
        target_location.text = (
            preserve_whitespace(
                translated,
                source_location.text or "",
            )
        )

    return target


def apply_leaf_translations(
    target: etree._Element,
    source: etree._Element,
    translated_segments: list[str],
) -> None:
    """
    Replace text locations in an existing target.

    XML elements themselves are never removed,
    reordered or recreated.
    """

    source_locations = (
        iter_text_locations(
            source
        )
    )

    target_locations = (
        iter_text_locations(
            target
        )
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

    for (
        source_location,
        target_location,
        translation,
    ) in zip(
        source_locations,
        target_locations,
        translated_segments,
    ):
        target_location.text = (
            preserve_whitespace(
                translation,
                source_location.text or "",
            )
        )


def validate_translation_tree(
    original_tree: etree._ElementTree,
    translated_tree: etree._ElementTree,
) -> None:
    """
    Verify that translation did not change the
    XLIFF structural skeleton.
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

        if original_structure != (
            translated_structure
        ):
            raise ValueError(
                f"Source structure changed in "
                f"trans-unit {original_id!r}"
            )

        translated_target = find_target(
            translated_unit
        )

        if translated_target is None:
            raise ValueError(
                f"Missing target in trans-unit "
                f"{original_id!r}"
            )

        source_structure = [
            (
                element.tag,
                dict(element.attrib),
                len(element),
            )
            for element in original_source.iter()
        ]

        target_structure = [
            (
                element.tag,
                dict(element.attrib),
                len(element),
            )
            for element in translated_target.iter()
        ]

        # target has the same hierarchy as source,
        # except for source -> target itself.
        if len(source_structure) != len(
            target_structure
        ):
            raise ValueError(
                f"Target structure changed in "
                f"trans-unit {original_id!r}"
            )

        for (
            source_info,
            target_info,
        ) in zip(
            source_structure,
            target_structure,
        ):
            source_tag = source_info[0]
            target_tag = target_info[0]

            source_local = etree.QName(
                source_tag
            ).localname

            target_local = etree.QName(
                target_tag
            ).localname

            if source_local == "source":
                if target_local != "target":
                    raise ValueError(
                        f"Expected target element in "
                        f"trans-unit {original_id!r}"
                    )
            elif source_info != target_info:
                raise ValueError(
                    f"Nested XML structure changed "
                    f"in trans-unit {original_id!r}"
                )


def inspect_xliff(
    path: str | Path,
) -> list[str]:
    """
    Produce a human-readable inspection.
    """

    tree = parse_xliff(path)

    units = find_trans_units(tree)

    lines: list[str] = []

    lines.append(
        f"XLIFF: {Path(path).name}"
    )

    lines.append(
        f"trans-units: {len(units)}"
    )

    lines.append("")

    for index, unit in enumerate(units):
        lines.append(
            f"[{index}] id={get_unit_id(unit)}"
        )

        source = find_source(unit)

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
            text = location.text or ""

            text = text.replace(
                "\n",
                "\\n",
            )

            lines.append(
                f"  leaf {leaf_index}: "
                f"{text!r}"
            )

        lines.append("")

    return lines