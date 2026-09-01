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


def translate_file(
    input_path: str | Path,
    output_dir: str | Path,
    languages: list[str],
    translator,
    dnt_path: str | Path | None = None,
    dnt_terms: list[str] | None = None,
) -> list[Path]:
    """
    Translate one XLIFF file into one output file
    for every requested target language.

    XML structure is preserved.

    DNT terms are enforced inside NLLB using constrained
    beam search rather than sending artificial DNT markers
    through the translation model.
    """

    input_path = Path(
        input_path
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------
    # Load DNT terms.
    # --------------------------------------------------

    loaded_dnt_terms: list[str] = []

    if dnt_path is not None:

        loaded_dnt_terms.extend(
            load_dnt_terms(
                dnt_path
            )
        )

    if dnt_terms:

        loaded_dnt_terms.extend(
            normalise_dnt_terms(
                dnt_terms
            )
        )

    loaded_dnt_terms = (
        normalise_dnt_terms(
            loaded_dnt_terms
        )
    )

    if loaded_dnt_terms:

        print(
            f"DNT terms loaded: "
            f"{len(loaded_dnt_terms)}"
        )

    outputs: list[Path] = []

    for language in languages:

        print()
        print("=" * 60)
        print(
            f"Translating -> {language}"
        )
        print("=" * 60)

        # --------------------------------------------------
        # Parse independent copies.
        # --------------------------------------------------

        original_tree = parse_xliff(
            input_path
        )

        working_tree = parse_xliff(
            input_path
        )

        # --------------------------------------------------
        # Build text-only translation tasks.
        # --------------------------------------------------

        tasks = build_translation_tasks(
            original_tree
        )

        original_units = find_trans_units(
            original_tree
        )

        working_units = find_trans_units(
            working_tree
        )

        if len(original_units) != len(
            working_units
        ):

            raise ValueError(
                "Original and working XLIFF "
                "have different trans-unit counts."
            )

        # --------------------------------------------------
        # Translation results.
        #
        # key:
        #
        #     (unit_index, location_index)
        #
        # value:
        #
        #     translated text
        # --------------------------------------------------

        translated_by_location: dict[
            tuple[int, int],
            str,
        ] = {}

        batch_size = getattr(
            translator,
            "batch_size",
            4,
        )

        # --------------------------------------------------
        # Translation batches.
        # --------------------------------------------------

        for start in tqdm(
            range(
                0,
                len(tasks),
                batch_size,
            ),
            total=(
                (
                    len(tasks)
                    + batch_size
                    - 1
                )
                // batch_size
            ),
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

            # --------------------------------------------------
            # Determine DNT terms actually present in each
            # text location.
            # --------------------------------------------------

            protected_terms_per_text = [
                find_dnt_terms_in_text(
                    text,
                    loaded_dnt_terms,
                )
                for text in texts
            ]

            # --------------------------------------------------
            # Normal path when no DNT feature is active.
            #
            # Keeping the old call signature here avoids
            # changing behaviour for normal translation.
            # --------------------------------------------------

            if not loaded_dnt_terms:

                translations = (
                    translator.translate_batch(
                        texts,
                        SOURCE_LANGUAGE,
                        language,
                    )
                )

            else:

                translations = (
                    translator.translate_batch(
                        texts,
                        SOURCE_LANGUAGE,
                        language,
                        protected_terms=(
                            protected_terms_per_text
                        ),
                    )
                )

            if len(translations) != len(
                batch_tasks
            ):

                raise ValueError(
                    "NLLB returned "
                    f"{len(translations)} "
                    "translations for "
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

        # --------------------------------------------------
        # Reconstruct target XML.
        # --------------------------------------------------

        translated_units_count = 0

        progress_units = tqdm(
            enumerate(
                working_units
            ),
            total=len(
                working_units
            ),
            desc=f"Rebuilding {language}",
            unit="unit",
        )

        for (
            unit_index,
            unit,
        ) in progress_units:

            source = find_source(
                unit
            )

            if source is None:
                continue

            locations = (
                iter_text_locations(
                    source
                )
            )

            translated_segments: list[
                str
            ] = []

            # --------------------------------------------------
            # Match translation results to the exact source
            # text location.
            # --------------------------------------------------

            for (
                location_index,
                location,
            ) in enumerate(
                locations
            ):

                key = (
                    unit_index,
                    location_index,
                )

                if key not in (
                    translated_by_location
                ):

                    raise ValueError(
                        "Missing translation for "
                        f"trans-unit "
                        f"{get_unit_id(unit)!r}, "
                        f"location "
                        f"{location_index}."
                    )

                translated_segments.append(
                    translated_by_location[
                        key
                    ]
                )

            # --------------------------------------------------
            # Build target from source structure.
            #
            # XML elements and attributes are preserved.
            # Only text/tail values are replaced.
            # --------------------------------------------------

            target = (
                build_translation_target(
                    source,
                    translated_segments,
                )
            )

            replace_or_add_target(
                trans_unit=unit,
                target_content=target,
            )

            if locations:
                translated_units_count += 1

        # --------------------------------------------------
        # Final XML validation.
        # --------------------------------------------------

        validate_translation_tree(
            original_tree=original_tree,
            translated_tree=working_tree,
        )

        # --------------------------------------------------
        # Output path.
        # --------------------------------------------------

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

        outputs.append(
            output_path
        )

    return outputs