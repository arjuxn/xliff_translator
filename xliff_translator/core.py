from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


@dataclass
class TranslationTask:
    """A single translatable text location in an XLIFF source."""

    unit_index: int
    location_index: int
    text: str


class TextLocation:
    """
    Reference to one text value inside an XML tree.

    Text can exist in two places in lxml:

    - element.text
    - child.tail

    Keeping the location as an object lets us replace only the
    text value while leaving the XML structure untouched.
    """

    def __init__(
        self,
        element: etree._Element,
        attribute: str,
    ) -> None:
        self.element = element
        self.attribute = attribute

    @property
    def text(self) -> str | None:
        return getattr(self.element, self.attribute)

    @text.setter
    def text(self, value: str) -> None:
        setattr(self.element, self.attribute, value)


def parse_xliff(
    path: str | Path,
) -> etree._ElementTree:
    """
    Parse an XLIFF file without removing insignificant XML content.

    The parser deliberately keeps:
    - whitespace
    - CDATA
    - comments
    - XML structure
    """

    parser = etree.XMLParser(
        remove_blank_text=False,
        resolve_entities=False,
        strip_cdata=False,
        remove_comments=False,
    )

    return etree.parse(str(path), parser)


def find_trans_units(
    tree: etree._ElementTree,
) -> list[etree._Element]:
    """Return all trans-unit elements in document order."""

    return tree.xpath(
        "//*[local-name()='trans-unit']"
    )


def get_unit_id(
    trans_unit: etree._Element,
) -> str:
    """Return the trans-unit ID."""

    return trans_unit.get("id", "")


def _find_direct_child(
    trans_unit: etree._Element,
    local_name: str,
) -> etree._Element | None:
    """Find a direct child using its local XML name."""

    for child in trans_unit:
        if etree.QName(child).localname == local_name:
            return child

    return None


def find_source(
    trans_unit: etree._Element,
) -> etree._Element | None:
    """Find the source element of a trans-unit."""

    return _find_direct_child(
        trans_unit,
        "source",
    )


def find_target(
    trans_unit: etree._Element,
) -> etree._Element | None:
    """Find the target element of a trans-unit."""

    return _find_direct_child(
        trans_unit,
        "target",
    )


def iter_text_locations(
    element: etree._Element,
) -> list[TextLocation]:
    """
    Return all translatable text/tail locations in document order.

    XML tags and attributes are deliberately excluded.

    For example:

        <source>
            Click <g id="1">START</g> to continue.
        </source>

    produces locations for:

        source.text
        g.text
        g.tail
    """

    locations: list[TextLocation] = []

    def walk(
        node: etree._Element,
    ) -> None:
        if node.text is not None:
            locations.append(
                TextLocation(
                    node,
                    "text",
                )
            )

        for child in node:
            walk(child)

            if child.tail is not None:
                locations.append(
                    TextLocation(
                        child,
                        "tail",
                    )
                )

    walk(element)

    return locations


def build_translation_tasks(
    tree: etree._ElementTree,
) -> list[TranslationTask]:
    """
    Extract every translatable source text location.

    The unit index and location index allow each translation to be
    placed back into the exact same XML location later.
    """

    tasks: list[TranslationTask] = []

    for unit_index, unit in enumerate(
        find_trans_units(tree)
    ):
        source = find_source(unit)

        if source is None:
            continue

        for location_index, location in enumerate(
            iter_text_locations(source)
        ):
            tasks.append(
                TranslationTask(
                    unit_index=unit_index,
                    location_index=location_index,
                    text=location.text or "",
                )
            )

    return tasks


def clone_source(
    source: etree._Element,
) -> etree._Element:
    """
    Deep-copy the source and turn the copy into a target.

    The original source tree is never modified.
    """

    target = deepcopy(source)

    qname = etree.QName(target)

    if qname.namespace:
        target.tag = (
            f"{{{qname.namespace}}}target"
        )
    else:
        target.tag = "target"

    return target


def apply_leaf_translations(
    target: etree._Element,
    source: etree._Element,
    translated_segments: list[str],
) -> None:
    """
    Replace only text/tail values in the copied target.

    XML tags, attributes, IDs, nesting, and ordering are not rebuilt.
    """

    source_locations = iter_text_locations(source)
    target_locations = iter_text_locations(target)

    if len(source_locations) != len(target_locations):
        raise ValueError(
            "Source and target have different "
            "numbers of text locations."
        )

    if len(translated_segments) != len(target_locations):
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
    """Create a target by cloning the source and replacing its text."""

    target = clone_source(source)

    apply_leaf_translations(
        target=target,
        source=source,
        translated_segments=translated_segments,
    )

    return target


def replace_or_add_target(
    trans_unit: etree._Element,
    target_content: etree._Element,
) -> etree._Element:
    """
    Replace an existing target or insert a new target after source.

    If an existing target is present, its tag, attributes, and
    namespace map are retained.
    """

    old_target = find_target(trans_unit)

    if old_target is not None:
        index = trans_unit.index(old_target)

        target = etree.Element(
            old_target.tag,
            attrib=dict(old_target.attrib),
            nsmap=old_target.nsmap,
        )

        target.text = target_content.text

        for child in target_content:
            target.append(deepcopy(child))

        trans_unit.remove(old_target)
        trans_unit.insert(index, target)

        return target

    source = find_source(trans_unit)

    if source is None:
        raise ValueError(
            f"trans-unit {get_unit_id(trans_unit)!r} "
            "has no source."
        )

    qname = etree.QName(source)

    if qname.namespace:
        target_tag = (
            f"{{{qname.namespace}}}target"
        )
    else:
        target_tag = "target"

    target = etree.Element(
        target_tag,
        nsmap=source.nsmap,
    )

    target.text = target_content.text

    for child in target_content:
        target.append(deepcopy(child))

    trans_unit.insert(
        trans_unit.index(source) + 1,
        target,
    )

    return target


def validate_translation_tree(
    original_tree: etree._ElementTree,
    translated_tree: etree._ElementTree,
) -> None:
    """
    Verify that translation did not change the source XML structure.

    The following are checked:

    - number of trans-units
    - trans-unit IDs
    - source element existence
    - source element tags
    - source element attributes
    - child counts
    - nesting/order
    """

    original_units = find_trans_units(
        original_tree
    )
    translated_units = find_trans_units(
        translated_tree
    )

    if len(original_units) != len(translated_units):
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


def inspect_xliff(
    path: str | Path,
) -> list[str]:
    """Return a human-readable inspection of an XLIFF file."""

    tree = parse_xliff(path)
    units = find_trans_units(tree)

    lines = [
        f"XLIFF: {Path(path).name}",
        f"trans-units: {len(units)}",
        "",
    ]

    for index, unit in enumerate(units):
        lines.append(
            f"[{index}] id={get_unit_id(unit)}"
        )

        source = find_source(unit)

        if source is None:
            lines.extend(
                [
                    "  source: MISSING",
                    "",
                ]
            )
            continue

        locations = iter_text_locations(source)

        if not locations:
            lines.extend(
                [
                    "  (markup-only / empty)",
                    "",
                ]
            )
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
                f"  leaf {leaf_index}: {text!r}"
            )

        lines.append("")

    return lines


def write_xliff(
    tree: etree._ElementTree,
    path: str | Path,
) -> None:
    """Write the translated XLIFF tree to disk."""

    path = Path(path)

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