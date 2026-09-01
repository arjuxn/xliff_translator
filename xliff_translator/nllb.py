from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
)

from .dnt import (
    count_dnt_terms,
    normalise_dnt_terms,
    validate_dnt_preservation,
)


@dataclass
class NLLBTranslator:

    model_name: str = (
        "facebook/nllb-200-distilled-600M"
    )

    device: str = "auto"

    max_input_tokens: int = 1024

    max_new_tokens: int = 1024

    batch_size: int = 4

    num_beams: int = 4

    def __post_init__(self):

        if self.device == "auto":

            self.device = (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )

        if (
            self.device.startswith("cuda")
            and not torch.cuda.is_available()
        ):

            raise RuntimeError(
                "CUDA was requested but "
                "PyTorch cannot access CUDA."
            )

        self.torch_device = torch.device(
            self.device
        )

        print(
            f"NLLB device: "
            f"{self.torch_device}"
        )

        if (
            self.torch_device.type
            == "cuda"
        ):

            gpu_index = (
                self.torch_device.index
                if self.torch_device.index
                is not None
                else torch.cuda.current_device()
            )

            print(
                "CUDA device: "
                f"{torch.cuda.get_device_name(gpu_index)}"
            )

        dtype = (
            torch.float16
            if self.torch_device.type
            == "cuda"
            else torch.float32
        )

        print(
            f"Loading tokenizer: "
            f"{self.model_name}"
        )

        self.tokenizer = (
            AutoTokenizer.from_pretrained(
                self.model_name,
                use_fast=True,
            )
        )

        print(
            f"Loading model: "
            f"{self.model_name}"
        )

        self.model = (
            AutoModelForSeq2SeqLM.from_pretrained(
                self.model_name,
                dtype=dtype,
            )
        )

        self.model.to(
            self.torch_device
        )

        self.model.eval()

        print(
            "NLLB model ready."
        )

    # ==========================================================
    # DNT PLACEHOLDER
    # ==========================================================

    def _placeholder(
        self,
        index: int,
    ) -> str:
        """
        Return a very distinctive placeholder.

        The placeholder is composed of ordinary alphabetic
        words rather than XML-like syntax or brackets.

        Example:

            XliffProtectedTermZero
        """

        names = [
            "Zero",
            "One",
            "Two",
            "Three",
            "Four",
            "Five",
            "Six",
            "Seven",
            "Eight",
            "Nine",
            "Ten",
            "Eleven",
            "Twelve",
            "Thirteen",
            "Fourteen",
            "Fifteen",
        ]

        if index < len(names):

            suffix = names[index]

        else:

            suffix = str(index)

        return (
            f"XliffProtectedTerm{suffix}"
        )

    def _protect_text(
        self,
        text: str,
        terms: Sequence[str],
    ) -> tuple[str, dict[str, str]]:

        from .dnt import (
            find_dnt_spans,
        )

        spans = find_dnt_spans(
            text,
            terms,
        )

        if not spans:
            return text, {}

        parts = []

        mapping: dict[str, str] = {}

        cursor = 0

        for index, (
            start,
            end,
            term,
        ) in enumerate(spans):

            placeholder = (
                self._placeholder(
                    index
                )
            )

            parts.append(
                text[cursor:start]
            )

            parts.append(
                placeholder
            )

            mapping[
                placeholder
            ] = term

            cursor = end

        parts.append(
            text[cursor:]
        )

        return (
            "".join(parts),
            mapping,
        )

    def _restore_text(
        self,
        text: str,
        mapping: dict[str, str],
    ) -> str:

        result = text

        for placeholder, term in (
            mapping.items()
        ):

            result = result.replace(
                placeholder,
                term,
            )

        return result

    # ==========================================================
    # SINGLE BATCH
    # ==========================================================

    def _generate_batch(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:

        if not texts:
            return []

        self.tokenizer.src_lang = (
            source_lang
        )

        forced_bos = (
            self.tokenizer.convert_tokens_to_ids(
                target_lang
            )
        )

        if forced_bos is None:

            raise ValueError(
                f"Unknown NLLB target language: "
                f"{target_lang}"
            )

        encoded = self.tokenizer(
            list(texts),
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_input_tokens,
        )

        encoded = {
            key: value.to(
                self.torch_device
            )
            for key, value
            in encoded.items()
        }

        with torch.inference_mode():

            if (
                self.torch_device.type
                == "cuda"
            ):

                with torch.autocast(
                    device_type="cuda",
                    dtype=torch.float16,
                ):

                    generated = (
                        self.model.generate(
                            **encoded,
                            forced_bos_token_id=(
                                forced_bos
                            ),
                            max_new_tokens=(
                                self.max_new_tokens
                            ),
                            num_beams=(
                                self.num_beams
                            ),
                            early_stopping=True,
                        )
                    )

            else:

                generated = (
                    self.model.generate(
                        **encoded,
                        forced_bos_token_id=(
                            forced_bos
                        ),
                        max_new_tokens=(
                            self.max_new_tokens
                        ),
                        num_beams=(
                            self.num_beams
                        ),
                        early_stopping=True,
                    )
                )

        return list(
            self.tokenizer.batch_decode(
                generated,
                skip_special_tokens=True,
            )
        )

    # ==========================================================
    # DNT TRANSLATION
    # ==========================================================

    def _translate_dnt_batch(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
        protected_terms: Sequence[
            Sequence[str]
        ],
    ) -> list[str]:

        protected_texts = []

        mappings = []

        for text, terms in zip(
            texts,
            protected_terms,
        ):

            protected, mapping = (
                self._protect_text(
                    text,
                    normalise_dnt_terms(
                        terms
                    ),
                )
            )

            protected_texts.append(
                protected
            )

            mappings.append(
                mapping
            )

        # ------------------------------------------------------
        # If no actual DNT term occurs in any item, use the
        # ordinary translation path.
        # ------------------------------------------------------

        if not any(mappings):

            return self._generate_batch(
                texts,
                source_lang,
                target_lang,
            )

        # ------------------------------------------------------
        # Translate the COMPLETE sentences.
        # ------------------------------------------------------

        translated = (
            self._generate_batch(
                protected_texts,
                source_lang,
                target_lang,
            )
        )

        if len(translated) != len(
            texts
        ):

            raise ValueError(
                "NLLB returned an unexpected "
                "number of translations."
            )

        outputs = []

        # ------------------------------------------------------
        # Restore DNT terms.
        # ------------------------------------------------------

        for (
            source,
            translation,
            mapping,
        ) in zip(
            texts,
            translated,
            mappings,
        ):

            missing = [
                marker
                for marker in mapping
                if marker not in translation
            ]

            if missing:

                # ------------------------------------------------
                # IMPORTANT:
                #
                # Never silently return a translation where
                # protected terms disappeared.
                # ------------------------------------------------

                missing_terms = [
                    mapping[marker]
                    for marker in missing
                ]

                raise ValueError(
                    "NLLB modified or removed "
                    "protected DNT terms. "
                    f"Missing: "
                    f"{missing_terms}"
                )

            restored = (
                self._restore_text(
                    translation,
                    mapping,
                )
            )

            validate_dnt_preservation(
                source,
                restored,
                mapping.values(),
            )

            outputs.append(
                restored
            )

        return outputs

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def translate_batch(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
        protected_terms: Sequence[
            Sequence[str]
        ] | None = None,
    ) -> list[str]:

        if not texts:
            return []

        if not source_lang:
            raise ValueError(
                "source_lang cannot be empty."
            )

        if not target_lang:
            raise ValueError(
                "target_lang cannot be empty."
            )

        outputs = []

        # ------------------------------------------------------
        # No DNT.
        # ------------------------------------------------------

        if protected_terms is None:

            for start in range(
                0,
                len(texts),
                self.batch_size,
            ):

                batch = list(
                    texts[
                        start:
                        start + self.batch_size
                    ]
                )

                outputs.extend(
                    self._generate_batch(
                        batch,
                        source_lang,
                        target_lang,
                    )
                )

            return outputs

        # ------------------------------------------------------
        # Validate DNT input.
        # ------------------------------------------------------

        if len(protected_terms) != len(
            texts
        ):

            raise ValueError(
                "protected_terms must contain "
                "one list per text."
            )

        # ------------------------------------------------------
        # We need to keep each text's own DNT mapping.
        #
        # Therefore DNT-enabled batches are processed as
        # individual items. This is slower, but correctness
        # comes first.
        # ------------------------------------------------------

        for text, terms in zip(
            texts,
            protected_terms,
        ):

            actual_terms = (
                normalise_dnt_terms(
                    terms
                )
            )

            actual_occurrences = (
                count_dnt_terms(
                    text,
                    actual_terms,
                )
            )

            if not actual_occurrences:

                translated = (
                    self._generate_batch(
                        [text],
                        source_lang,
                        target_lang,
                    )
                )

                outputs.extend(
                    translated
                )

                continue

            translated = (
                self._translate_dnt_batch(
                    [text],
                    source_lang,
                    target_lang,
                    [actual_terms],
                )
            )

            outputs.extend(
                translated
            )

        return outputs