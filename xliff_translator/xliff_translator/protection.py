"""
Protection layer for XLIFF inline elements.

The purpose of this module is to convert XML containing inline elements
into a translation-safe representation for NLLB, while keeping enough
information to reconstruct the original XML structure afterward.

Example:

    <source>
        Click <g id="1">START</g> to begin.
    </source>

becomes:

    Click [[XLIFF_G_1_START]]START[[XLIFF_G_1_END]] to begin.

The XML elements themselves are NOT sent to NLLB as XML.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from lxml import etree


@dataclass
class ProtectedText:
    """
    Translation-ready text plus information about protected elements.
    """

    text: str
    markers: Dict[str, etree._Element]


def _marker_name(element: etree._Element, index: int) -> str:
    """
    Create a deterministic marker for an inline XML element.

    We prefer the XLIFF element's id when available, but also include
    an index so duplicate IDs cannot accidentally collide.
    """

    element_id = element.get("id")

    if element_id:
        safe_id = "".join(
            character if character.isalnum() else "_"
            for character in element_id
        )
        return f"XLIFF_G_{safe_id}_{index}"

    return f"XLIFF_G_{index}"


def protect_source(source: etree._Element) -> ProtectedText:
    """
    Convert an XLIFF <source> element into a translation-safe string.

    All XML elements inside <source> are represented using markers.
    Their actual XML nodes are retained in the marker dictionary.

    Text and tail text are both preserved.

    Example:

        <source>Hello <g id="1">world</g>!</source>

    becomes approximately:

        Hello [[XLIFF_G_1_0_START]]world[[XLIFF_G_1_0_END]]!

    """

    markers: Dict[str, etree._Element] = {}
    parts: list[str] = []
    counter = 0

    def visit(element: etree._Element) -> None:
        nonlocal counter

        if element.text:
            parts.append(element.text)

        for child in element:
            marker = _marker_name(child, counter)
            counter += 1

            markers[marker] = child

            parts.append(f"[[{marker}_START]]")

            visit(child)

            parts.append(f"[[{marker}_END]]")

            if child.tail:
                parts.append(child.tail)

    visit(source)

    return ProtectedText(
        text="".join(parts),
        markers=markers,
    )


def validate_markers(
    translated_text: str,
    protected: ProtectedText,
) -> None:
    """
    Verify that NLLB did not destroy our protected markers.

    Raises ValueError if any required marker disappeared.
    """

    missing: list[str] = []

    for marker in protected.markers:
        start_marker = f"[[{marker}_START]]"
        end_marker = f"[[{marker}_END]]"

        if start_marker not in translated_text:
            missing.append(start_marker)

        if end_marker not in translated_text:
            missing.append(end_marker)

    if missing:
        raise ValueError(
            "NLLB modified or removed protected XLIFF markers: "
            + ", ".join(missing)
        )