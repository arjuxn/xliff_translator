from __future__ import annotations

import re
from copy import deepcopy

from lxml import etree


MARKER_RE = re.compile(
    r"\[\[XLIFF_G_(?P<id>.+?)_(?P<index>\d+)_(?P<kind>START|END)\]\]"
)


def _marker_pattern(
    element_id: str,
    index: int,
    kind: str,
) -> str:
    return (
        f"[[XLIFF_G_{element_id}_{index}_{kind}]]"
    )


def _collect_g_elements(
    source: etree._Element,
) -> list[etree._Element]:
    """
    Collect every <g> element in document order.

    The order MUST match the order used by protection.py
    when creating marker indexes.
    """

    return [
        element
        for element in source.iter()
        if etree.QName(element).localname == "g"
    ]


def _build_marker_map(
    source: etree._Element,
) -> dict[tuple[str, int], etree._Element]:
    """
    Build:

        (g_id, marker_index) -> original <g>

    This lets us recover the exact original element
    when we encounter its markers in the translation.
    """

    result: dict[
        tuple[str, int],
        etree._Element,
    ] = {}

    g_elements = _collect_g_elements(source)

    for index, element in enumerate(g_elements):

        element_id = element.get("id")

        if element_id is None:
            raise ValueError(
                "Encountered <g> without an id."
            )

        result[
            (element_id, index)
        ] = element

    return result


def _find_matching_marker(
    text: str,
    position: int,
):
    """
    Find the next XLIFF marker beginning at or after
    position.
    """

    return MARKER_RE.search(
        text,
        position,
    )


def _set_text(
    element: etree._Element,
    value: str,
) -> None:
    """
    Set element.text while preserving the XML element
    itself.
    """

    element.text = value


def _append_tail(
    element: etree._Element,
    value: str,
) -> None:
    """
    Set the tail text belonging to an element.

    In:

        <g>hello</g> world

    ' world' belongs to g.tail.
    """

    element.tail = value


def _parse_marker(
    marker: re.Match,
):
    """
    Return:

        element id
        marker index
        START / END
    """

    return (
        marker.group("id"),
        int(marker.group("index")),
        marker.group("kind"),
    )


def reconstruct_target(
    source: etree._Element,
    translated: str,
    protected: str | None = None,
) -> etree._Element:
    """
    Reconstruct a translated target from the original
    source structure and protected translated text.

    The ORIGINAL XML tree is used as the structural
    template.

    Only text values are replaced.

    Nested <g> elements, attributes, namespaces,
    children, and ordering are preserved.

    Example:

        source:

            <g id="outer">
                Hello
                <g id="inner">world</g>
                !
            </g>

        translated:

            [[XLIFF_G_outer_0_START]]
            Bonjour
            [[XLIFF_G_inner_1_START]]
            monde
            [[XLIFF_G_inner_1_END]]
            !
            [[XLIFF_G_outer_0_END]]

        result:

            <g id="outer">
                Bonjour
                <g id="inner">monde</g>
                !
            </g>
    """

    if protected is None:
        protected = ""

    target = deepcopy(source)

    marker_map = _build_marker_map(source)

    # --------------------------------------------------
    # No protected markers
    # --------------------------------------------------

    if not marker_map:

        locations = _text_locations(
            target
        )

        if locations:

            locations[0][0].__setattr__(
                locations[0][1],
                translated,
            )

        else:

            target.text = translated

        return target

    # --------------------------------------------------
    # Parse translation into a nested structure
    # --------------------------------------------------

    root_frame = {
        "element": target,
        "buffer": "",
        "last_child": None,
    }

    stack = [root_frame]

    position = 0

    markers_found = 0

    while True:

        marker = _find_matching_marker(
            translated,
            position,
        )

        if marker is None:

            remainder = translated[position:]

            stack[-1]["buffer"] += remainder

            break

        # Text BEFORE this marker belongs to the
        # currently active element.

        before = translated[
            position:marker.start()
        ]

        stack[-1]["buffer"] += before

        (
            element_id,
            index,
            kind,
        ) = _parse_marker(marker)

        key = (
            element_id,
            index,
        )

        if key not in marker_map:
            raise ValueError(
                "Unknown XLIFF marker: "
                f"{marker.group(0)}"
            )

        original_element = marker_map[key]

        if kind == "START":

            markers_found += 1

            # Find the corresponding element in
            # the cloned target tree.

            target_element = _find_corresponding_element(
                source,
                target,
                original_element,
            )

            if target_element is None:
                raise ValueError(
                    "Could not locate corresponding "
                    f"<g id={element_id!r}> in target."
                )

            # Text accumulated immediately before
            # the nested element belongs to the
            # current parent.

            _flush_frame_text(
                stack[-1]
            )

            # Attach the nested element to the
            # current parent if necessary.

            parent = stack[-1]["element"]

            if target_element.getparent() is not parent:

                if target_element.getparent() is not None:
                    target_element.getparent().remove(
                        target_element
                    )

                parent.append(
                    target_element
                )

            # Start a new frame for this element.

            stack.append(
                {
                    "element": target_element,
                    "buffer": "",
                    "last_child": None,
                }
            )

        else:

            markers_found += 1

            if len(stack) <= 1:
                raise ValueError(
                    "Unexpected XLIFF END marker: "
                    f"{marker.group(0)}"
                )

            current = stack[-1]

            expected_element = current[
                "element"
            ]

            expected_id = (
                expected_element.get("id")
            )

            if expected_id != element_id:
                raise ValueError(
                    "Mismatched nested XLIFF markers. "
                    f"Expected END for {expected_id!r}, "
                    f"got {element_id!r}."
                )

            # Everything accumulated inside this
            # element becomes its text.

            _flush_frame_text(
                current
            )

            stack.pop()

            parent = stack[-1]

            parent["last_child"] = (
                current["element"]
            )

        position = marker.end()

    # --------------------------------------------------
    # Close all nested elements
    # --------------------------------------------------

    if len(stack) != 1:

        unclosed = [
            frame["element"].get("id")
            for frame in stack[1:]
        ]

        raise ValueError(
            "Unclosed XLIFF markers for: "
            + ", ".join(
                repr(value)
                for value in unclosed
            )
        )

    _flush_frame_text(
        stack[0]
    )

    if markers_found == 0:

        raise ValueError(
            "Translated text contained no "
            "recognized XLIFF markers."
        )

    return target


def _flush_frame_text(
    frame,
) -> None:
    """
    Put buffered translated text into the correct
    XML text location.

    For a normal element:

        <g>TEXT</g>

    the text belongs in:

        element.text

    For text occurring AFTER a nested child:

        <g>
            <g>child</g>TAIL
        </g>

    the text belongs in:

        child.tail
    """

    text = frame["buffer"]

    frame["buffer"] = ""

    if text == "":
        return

    element = frame["element"]

    last_child = frame["last_child"]

    if last_child is None:

        # Text before the first child.

        element.text = text

    else:

        # Text after the most recently closed child.

        last_child.tail = text


def _find_corresponding_element(
    source_root: etree._Element,
    target_root: etree._Element,
    source_element: etree._Element,
) -> etree._Element | None:
    """
    Find the element in the deepcopy(target_root)
    corresponding to source_element.

    We use the structural path rather than merely
    searching by id, because IDs are not guaranteed
    to be globally unique.
    """

    path: list[int] = []

    current = source_element

    while current is not source_root:

        parent = current.getparent()

        if parent is None:
            return None

        path.append(
            parent.index(current)
        )

        current = parent

    path.reverse()

    result = target_root

    for child_index in path:

        if child_index >= len(result):
            return None

        result = result[child_index]

    return result


def _text_locations(
    element: etree._Element,
):
    """
    Return all text/tail locations.

    Kept private because reconstruction itself is
    marker-driven.
    """

    locations = []

    def walk(node):

        if node.text is not None:
            locations.append(
                (
                    node,
                    "text",
                )
            )

        for child in node:

            walk(child)

            if child.tail is not None:
                locations.append(
                    (
                        child,
                        "tail",
                    )
                )

    walk(element)

    return locations