from __future__ import annotations

from pathlib import Path

from tqdm import tqdm

from .core import (
    build_translation_target,
    build_translation_tasks,
    find_source,
    find_trans_units,
    get_unit_id,
    iter_text_locations,
    parse_xliff,
    replace_or_add_target,
    validate_translation_tree,
    write_xliff,
)
from .dnt import (
    find_dnt_terms_in_text,
    load_dnt_terms,
    normalise_dnt_terms,
)


SOURCE_LANGUAGE = "eng_Latn"


def _load_dnt_terms(
    dnt_path: str | Path | None,
    dnt_terms: list[str] | None,
) -> list[str]:
    """Load and normalize DNT terms from all configured sources."""

    terms: list[str] = []

    if dnt_path is not None:
        terms.extend(
            load_dnt_terms(dnt_path)
        )

    if dnt_terms:
        terms.extend(dnt_terms)

    return normalise_dnt_terms(terms)


def _translate_tasks(
    tasks,
    translator,
    language: str,
    protected_terms: list[str],
) -> dict[tuple[int, int], str]:
    """
    Translate tasks and map each result back to its XML location.
    """

    if not tasks:
        return {}

    batch_size = max(
        1,
        int(
            getattr(
                translator,
                "batch_size",
                4,
            )
        ),
    )

    translated_by_location: dict[
        tuple[int, int],
        str,
    ] = {}

    total_batches = (
        len(tasks) + batch_size - 1
    ) // batch_size

    for start in tqdm(
        range(
            0,
            len(tasks),
            batch_size,
        ),
        total=total_batches,
        desc=f"NLLB {language}",
        unit="batch",
    ):
        batch_tasks = tasks[
            start:
            start + batch_size
        ]

        texts = [
            task.text
            for task in batch_tasks
        ]

        if protected_terms:
            protected_terms_per_text = [
                find_dnt_terms_in_text(
                    text,
                    protected_terms,
                )
                for text in texts
            ]

            translations = translator.translate_batch(
                texts,
                SOURCE_LANGUAGE,
                language,
                protected_terms=(
                    protected_terms_per_text
                ),
            )

        else:
            translations = translator.translate_batch(
                texts,
                SOURCE_LANGUAGE,
                language,
            )

        if len(translations) != len(batch_tasks):
            raise ValueError(
                "NLLB returned "
                f"{len(translations)} translations "
                "for "
                f"{len(batch_tasks)} inputs."
            )

        for task, translation in zip(
            batch_tasks,
            translations,
        ):
            translated_by_location[
                (
                    task.unit_index,
                    task.location_index,
                )
            ] = translation

    return translated_by_location


def _rebuild_targets(
    working_tree,
    translated_by_location: dict[
        tuple[int, int],
        str,
    ],
    language: str,
) -> int:
    """Rebuild all target elements from translated text values."""

    working_units = find_trans_units(
        working_tree
    )

    translated_units_count = 0

    progress = tqdm(
        enumerate(working_units),
        total=len(working_units),
        desc=f"Rebuilding {language}",
        unit="unit",
    )

    for unit_index, unit in progress:
        source = find_source(unit)

        if source is None:
            continue

        locations = iter_text_locations(
            source
        )

        if not locations:
            continue

        translated_segments: list[str] = []

        for location_index in range(
            len(locations)
        ):
            key = (
                unit_index,
                location_index,
            )

            if key not in translated_by_location:
                raise ValueError(
                    "Missing translation for "
                    f"trans-unit "
                    f"{get_unit_id(unit)!r}, "
                    f"location "
                    f"{location_index}."
                )

            translated_segments.append(
                translated_by_location[key]
            )

        target = build_translation_target(
            source,
            translated_segments,
        )

        replace_or_add_target(
            trans_unit=unit,
            target_content=target,
        )

        translated_units_count += 1

    return translated_units_count


def translate_file(
    input_path: str | Path,
    output_dir: str | Path,
    languages: list[str],
    translator,
    dnt_path: str | Path | None = None,
    dnt_terms: list[str] | None = None,
) -> list[Path]:
    """
    Translate an XLIFF file into one output file per target language.

    XML structure is preserved by cloning each source element and
    replacing only its text/tail values with translated strings.
    """

    input_path = Path(input_path)
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    protected_terms = _load_dnt_terms(
        dnt_path=dnt_path,
        dnt_terms=dnt_terms,
    )

    if protected_terms:
        print(
            f"DNT terms loaded: "
            f"{len(protected_terms)}"
        )

    outputs: list[Path] = []

    for language in languages:
        print()
        print("=" * 60)
        print(f"Translating -> {language}")
        print("=" * 60)

        original_tree = parse_xliff(
            input_path
        )

        working_tree = parse_xliff(
            input_path
        )

        original_units = find_trans_units(
            original_tree
        )

        working_units = find_trans_units(
            working_tree
        )

        if len(original_units) != len(working_units):
            raise ValueError(
                "Original and working XLIFF "
                "have different trans-unit counts."
            )

        tasks = build_translation_tasks(
            original_tree
        )

        translated_by_location = _translate_tasks(
            tasks=tasks,
            translator=translator,
            language=language,
            protected_terms=protected_terms,
        )

        translated_units_count = _rebuild_targets(
            working_tree=working_tree,
            translated_by_location=translated_by_location,
            language=language,
        )

        validate_translation_tree(
            original_tree=original_tree,
            translated_tree=working_tree,
        )

        output_path = (
            output_dir
            / (
                f"{input_path.stem}."
                f"{language}."
                f"{input_path.suffix.lstrip('.')}"
            )
        )

        write_xliff(
            working_tree,
            output_path,
        )

        print()
        print(
            f"Completed {language}: "
            f"{translated_units_count}/"
            f"{len(working_units)} units"
        )

        print(
            f"Output: {output_path}"
        )

        outputs.append(output_path)

    return outputs