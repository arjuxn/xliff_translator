from __future__ import annotations

from pathlib import Path
from typing import Iterable


def load_dnt_terms(
    path: str | Path,
) -> list[str]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"DNT file not found: {path}"
        )

    text = path.read_text(
        encoding="utf-8-sig"
    )

    return normalise_dnt_terms(
        text.splitlines()
    )


def normalise_dnt_terms(
    terms: Iterable[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for raw_term in terms:

        term = str(raw_term).strip()

        if not term:
            continue

        if term in seen:
            continue

        seen.add(term)
        result.append(term)

    return result


def _word_character(
    character: str,
) -> bool:
    return (
        character.isalnum()
        or character == "_"
    )


def _has_left_boundary(
    text: str,
    start: int,
) -> bool:

    if start == 0:
        return True

    return not _word_character(
        text[start - 1]
    )


def _has_right_boundary(
    text: str,
    end: int,
) -> bool:

    if end >= len(text):
        return True

    return not _word_character(
        text[end]
    )


def find_dnt_spans(
    text: str,
    terms: Iterable[str],
) -> list[tuple[int, int, str]]:

    normalised = normalise_dnt_terms(
        terms
    )

    if not text or not normalised:
        return []

    ordered_terms = sorted(
        normalised,
        key=len,
        reverse=True,
    )

    candidates = []

    for term in ordered_terms:

        start = 0

        while True:

            position = text.find(
                term,
                start,
            )

            if position == -1:
                break

            end = (
                position
                + len(term)
            )

            if (
                _has_left_boundary(
                    text,
                    position,
                )
                and _has_right_boundary(
                    text,
                    end,
                )
            ):

                candidates.append(
                    (
                        position,
                        end,
                        term,
                    )
                )

            start = position + 1

    candidates.sort(
        key=lambda item: (
            item[0],
            -(item[1] - item[0]),
        )
    )

    selected = []

    occupied_until = -1

    for start, end, term in candidates:

        if start < occupied_until:
            continue

        selected.append(
            (
                start,
                end,
                term,
            )
        )

        occupied_until = end

    return selected


def find_dnt_terms_in_text(
    text: str,
    terms: Iterable[str],
) -> list[str]:

    return [
        term
        for _, _, term
        in find_dnt_spans(
            text,
            terms,
        )
    ]


def count_dnt_terms(
    text: str,
    terms: Iterable[str],
) -> dict[str, int]:

    counts: dict[str, int] = {}

    for term in find_dnt_terms_in_text(
        text,
        terms,
    ):

        counts[term] = (
            counts.get(term, 0)
            + 1
        )

    return counts


def validate_dnt_preservation(
    source_text: str,
    translated_text: str,
    terms: Iterable[str],
) -> None:

    source_counts = count_dnt_terms(
        source_text,
        terms,
    )

    if not source_counts:
        return

    translated_counts = count_dnt_terms(
        translated_text,
        source_counts.keys(),
    )

    for term, expected in (
        source_counts.items()
    ):

        actual = translated_counts.get(
            term,
            0,
        )

        if actual != expected:

            raise ValueError(
                "DNT term was not preserved "
                "exactly: "
                f"{term!r}. "
                f"Expected {expected} "
                f"occurrence(s), got {actual}."
            )


def protect_dnt_terms(
    text: str,
    terms: Iterable[str],
) -> tuple[str, dict[str, str]]:

    spans = find_dnt_spans(
        text,
        terms,
    )

    if not spans:
        return text, {}

    mapping: dict[str, str] = {}

    parts = []

    cursor = 0

    for index, (
        start,
        end,
        term,
    ) in enumerate(spans):

        marker = (
            f"[[XLIFF_DNT_{index}]]"
        )

        parts.append(
            text[cursor:start]
        )

        parts.append(
            marker
        )

        mapping[marker] = term

        cursor = end

    parts.append(
        text[cursor:]
    )

    return (
        "".join(parts),
        mapping,
    )


def restore_dnt_terms(
    text: str,
    mapping: dict[str, str],
) -> str:

    result = text

    for marker, term in mapping.items():

        result = result.replace(
            marker,
            term,
        )

    return result


def validate_dnt_markers(
    text: str,
    mapping: dict[str, str],
) -> None:

    for marker in mapping:

        count = text.count(
            marker
        )

        if count != 1:

            raise ValueError(
                "DNT marker validation failed: "
                f"{marker!r} occurred "
                f"{count} time(s)."
            )