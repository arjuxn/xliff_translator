from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from lxml import etree


@dataclass
class TextLocation:
    """
    Identifies one piece of text inside an XML tree.

    The text can live in:
      element.text
    or:
      previous_child.tail
    """

    index: int
    element: etree._Element
    is_tail: bool
    text: str


@dataclass
class TranslationJob:
    """
    One piece of text sent to the translation engine.

    For now, one TranslationJob normally represents one <source>.
    """

    unit_id: str
    text: str
    locations: list[TextLocation]
    protected: bool = False


def iter_text_locations(source: etree._Element) -> list[TextLocation]:
    """
    Walk a source subtree and collect every translatable text node.

    IMPORTANT:
    XML has two places where text can live:

        <g>Hello</g>
             ^ element.text

    and:

        <g>Hello</g> world
                      ^ child.tail

    Both must be captured.
    """

    locations: list[TextLocation] = []

    def walk(element: etree._Element) -> None:
        if element.text and element.text.strip():
            locations.append(
                TextLocation(
                    index=len(locations),
                    element=element,
                    is_tail=False,
                    text=element.text,
                )
            )

        for child in element:
            walk(child)

            if child.tail and child.tail.strip():
                locations.append(
                    TextLocation(
                        index=len(locations),
                        element=child,
                        is_tail=True,
                        text=child.tail,
                    )
                )

    walk(source)

    return locations


def combined_text(locations: Iterable[TextLocation]) -> str:
    """
    Combine text leaves into one linguistic string.

    Whitespace-only XML formatting is ignored.
    """

    pieces = []

    for location in locations:
        text = location.text.strip()

        if text:
            pieces.append(text)

    return " ".join(pieces)


def make_translation_job(
    unit_id: str,
    source: etree._Element,
) -> TranslationJob | None:
    """
    Build a translation job from one <source>.
    """

    locations = iter_text_locations(source)

    if not locations:
        return None

    text = combined_text(locations)

    if not text.strip():
        return None

    protected = len(locations) > 1 or len(source) > 0

    return TranslationJob(
        unit_id=unit_id,
        text=text,
        locations=locations,
        protected=protected,
    )


def build_protected_text(job: TranslationJob) -> str:
    """
    Build the string sent to NLLB.

    Each original text fragment receives a marker.

    Example:

        Click
        START
        to begin.

    becomes approximately:

        [XLFSEG000]Click[XLFSEG001]
        START[XLFSEG002]
        to begin.[XLFSEG003]

    The markers are NOT written into the final XLF.
    """

    parts: list[str] = []

    for location in job.locations:
        marker_start = f"XLFSEG{location.index:04d}A"
        marker_end = f"XLFSEG{location.index:04d}B"

        parts.append(marker_start)
        parts.append(location.text.strip())
        parts.append(marker_end)

    return " ".join(parts)


def extract_protected_segments(
    translated: str,
    expected_count: int,
) -> list[str] | None:
    """
    Extract translated text between our markers.

    Returns None if NLLB modified, removed, duplicated,
    or reordered the markers.
    """

    segments: list[str] = []

    cursor = 0

    for index in range(expected_count):
        start = f"XLFSEG{index:04d}A"
        end = f"XLFSEG{index:04d}B"

        start_pos = translated.find(start, cursor)

        if start_pos == -1:
            return None

        end_pos = translated.find(end, start_pos + len(start))

        if end_pos == -1:
            return None

        text = translated[start_pos + len(start):end_pos].strip()

        segments.append(text)

        cursor = end_pos + len(end)

    # There must not be another marker after the last expected marker.
    remaining = translated[cursor:]

    if "XLFSEG" in remaining:
        return None

    # Make sure every marker occurs exactly once.
    for index in range(expected_count):
        start = f"XLFSEG{index:04d}A"
        end = f"XLFSEG{index:04d}B"

        if translated.count(start) != 1:
            return None

        if translated.count(end) != 1:
            return None

    return segments


def normalise_leaf_translation(
    translated: str,
    original: str,
) -> str:
    """
    Preserve leading/trailing whitespace from the original text node.

    NLLB should translate the meaningful text, not XML indentation.
    """

    leading = original[: len(original) - len(original.lstrip())]
    trailing = original[len(original.rstrip()):]

    return f"{leading}{translated.strip()}{trailing}"


def apply_leaf_translations(
    target: etree._Element,
    source: etree._Element,
    translated_segments: list[str],
) -> None:
    """
    Put translated leaves into an exact clone of the source structure.

    The structure itself is NEVER reconstructed from model output.
    """

    target_locations = iter_text_locations(target)
    source_locations = iter_text_locations(source)

    if len(target_locations) != len(source_locations):
        raise ValueError(
            "Internal error: source/target text-node counts differ."
        )

    if len(target_locations) != len(translated_segments):
        raise ValueError(
            "Translation segment count does not match XML text-node count."
        )

    for location, original_location, translated in zip(
        target_locations,
        source_locations,
        translated_segments,
    ):
        value = normalise_leaf_translation(
            translated,
            original_location.text,
        )

        if location.is_tail:
            location.element.tail = value
        else:
            location.element.text = value


def clone_source(source: etree._Element) -> etree._Element:
    """
    Make an exact XML copy of <source>.

    This is the foundation of structure preservation.
    """

    return etree.fromstring(
        etree.tostring(source, encoding="utf-8")
    )