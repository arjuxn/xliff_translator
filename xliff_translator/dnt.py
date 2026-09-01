from __future__ import annotations

from pathlib import Path
from typing import Iterable


def normalise_dnt_terms(
    terms: Iterable[str],
) -> list[str]:
    """
    Normalize a collection of DNT terms.

    Terms are stripped of surrounding whitespace.
    Empty terms are ignored.
    Duplicate terms are removed while preserving order.
    Matching remains case-sensitive.
    """

    result: list[str] = []
    seen: set[str] = set()

    for raw_term in terms:
        term = str(raw_term).strip()

        if not term or term in seen:
            continue

        seen.add(term)
        result.append(term)

    return result


def load_dnt_terms(
    path: str | Path,
) -> list[str]:
    """
    Load DNT terms from a UTF-8 text file.

    The expected format is one term per line.
    UTF-8 BOMs are handled automatically.
    """

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


def _is_word_character(
    character: str,
) -> bool:
    """Return whether a character belongs to a word."""

    return (
        character.isalnum()
        or character == "_"
    )


def _has_left_boundary(
    text: str,
    start: int,
) -> bool:
    """Check the left boundary of a potential DNT match."""

    if start == 0:
        return True

    return not _is_word_character(
        text[start - 1]
    )


def _has_right_boundary(
    text: str,
    end: int,
) -> bool:
    """Check the right boundary of a potential DNT match."""

    if end >= len(text):
        return True

    return not _is_word_character(
        text[end]
    )


def find_dnt_spans(
    text: str,
    terms: Iterable[str],
) -> list[tuple[int, int, str]]:
    """
    Find DNT term occurrences in text.

    Matching is:
    - case-sensitive
    - boundary-aware
    - longest-term-first for overlapping terms

    Returns:
        (start, end, matched_term)
    """

    if not text:
        return []

    normalised_terms = normalise_dnt_terms(
        terms
    )

    if not normalised_terms:
        return []

    # Longer terms must be considered first so that an overlapping
    # term does not consume part of a longer protected term.
    ordered_terms = sorted(
        normalised_terms,
        key=len,
        reverse=True,
    )

    candidates: list[
        tuple[int, int, str]
    ] = []

    for term in ordered_terms:
        search_start = 0

        while True:
            position = text.find(
                term,
                search_start,
            )

            if position == -1:
                break

            end = position + len(term)

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

            # Move forward even after a match so multiple occurrences
            # of the same term are detected.
            search_start = position + 1

    # Earlier positions first; for identical starting positions,
    # prefer the longest match.
    candidates.sort(
        key=lambda item: (
            item[0],
            -(item[1] - item[0]),
        )
    )

    selected: list[
        tuple[int, int, str]
    ] = []

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
    """Return DNT terms occurring in the supplied text."""

    return [
        term
        for _, _, term in find_dnt_spans(
            text,
            terms,
        )
    ]


def count_dnt_terms(
    text: str,
    terms: Iterable[str],
) -> dict[str, int]:
    """Count occurrences of each DNT term in text."""

    counts: dict[str, int] = {}

    for term in find_dnt_terms_in_text(
        text,
        terms,
    ):
        counts[term] = (
            counts.get(term, 0) + 1
        )

    return counts


def validate_dnt_preservation(
    source_text: str,
    translated_text: str,
    terms: Iterable[str],
) -> None:
    """
    Verify that DNT terms occurring in the source occur the same
    number of times in the translated text.
    """

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

    for term, expected_count in source_counts.items():
        actual_count = translated_counts.get(
            term,
            0,
        )

        if actual_count != expected_count:
            raise ValueError(
                "DNT term was not preserved exactly: "
                f"{term!r}. "
                f"Expected {expected_count} occurrence(s), "
                f"got {actual_count}."
            )


def protect_dnt_terms(
    text: str,
    terms: Iterable[str],
) -> tuple[str, dict[str, str]]:
    """
    Replace DNT terms with temporary markers.

    This helper is retained for compatibility with the DNT tests and
    public module API. The main XLIFF pipeline uses the NLLB-specific
    placeholder mechanism instead.
    """

    spans = find_dnt_spans(
        text,
        terms,
    )

    if not spans:
        return text, {}

    mapping: dict[str, str] = {}
    parts: list[str] = []
    cursor = 0

    for index, (start, end, term) in enumerate(
        spans
    ):
        marker = (
            f"[[XLIFF_DNT_{index}]]"
        )

        parts.append(
            text[cursor:start]
        )
        parts.append(marker)

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
    """Restore DNT terms from temporary markers."""

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
    """Verify that every temporary DNT marker survived."""

    for marker in mapping:
        count = text.count(marker)

        if count != 1:
            raise ValueError(
                "DNT marker validation failed: "
                f"{marker!r} occurred {count} time(s)."
            )