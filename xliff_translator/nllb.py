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
    find_dnt_spans,
    normalise_dnt_terms,
    validate_dnt_preservation,
)


@dataclass
class NLLBTranslator:
    """NLLB-200 translation engine with optional DNT protection."""

    model_name: str = (
        "facebook/nllb-200-distilled-600M"
    )
    device: str = "auto"
    max_input_tokens: int = 1024
    max_new_tokens: int = 1024
    batch_size: int = 4
    num_beams: int = 4

    def __post_init__(self) -> None:
        self.torch_device = self._resolve_device()

        print(
            f"NLLB device: {self.torch_device}"
        )

        if self.torch_device.type == "cuda":
            gpu_index = (
                self.torch_device.index
                if self.torch_device.index is not None
                else torch.cuda.current_device()
            )

            print(
                "CUDA device: "
                f"{torch.cuda.get_device_name(gpu_index)}"
            )

        dtype = (
            torch.float16
            if self.torch_device.type == "cuda"
            else torch.float32
        )

        print(
            f"Loading tokenizer: {self.model_name}"
        )

        self.tokenizer = (
            AutoTokenizer.from_pretrained(
                self.model_name,
                use_fast=True,
            )
        )

        print(
            f"Loading model: {self.model_name}"
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

        print("NLLB model ready.")

    def _resolve_device(self) -> torch.device:
        """Resolve and validate the requested execution device."""

        if self.device == "auto":
            device_name = (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        else:
            device_name = self.device

        if (
            device_name.startswith("cuda")
            and not torch.cuda.is_available()
        ):
            raise RuntimeError(
                "CUDA was requested but "
                "PyTorch cannot access CUDA."
            )

        return torch.device(
            device_name
        )

    @staticmethod
    def _placeholder(
        index: int,
    ) -> str:
        """
        Create a temporary placeholder for a DNT term.

        The placeholder is intentionally made from ordinary
        alphabetic characters because NLLB handles these more
        reliably than XML-like marker syntax.
        """

        names = (
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
        )

        suffix = (
            names[index]
            if index < len(names)
            else str(index)
        )

        return (
            f"XliffProtectedTerm{suffix}"
        )

    @staticmethod
    def _normalise_placeholder(
        text: str,
    ) -> str:
        """
        Normalize whitespace inside an NLLB-generated placeholder.

        NLLB may tokenize a placeholder such as:

            XliffProtectedTermZero

        and generate:

            Xliff ProtectedTermZero

        Removing whitespace allows us to recognize the placeholder
        without allowing arbitrary text to be mistaken for it.
        """

        return "".join(
            text.split()
        )

    def _find_generated_placeholder(
        self,
        text: str,
        placeholder: str,
    ) -> tuple[int, int] | None:
        """
        Find a placeholder in NLLB output.

        NLLB may insert whitespace inside the placeholder. We therefore
        compare a whitespace-normalized representation while returning
        the original span from the generated text.
        """

        normalized_placeholder = (
            self._normalise_placeholder(
                placeholder
            )
        )

        if not normalized_placeholder:
            return None

        normalized_output: list[str] = []
        original_positions: list[int] = []

        for index, character in enumerate(text):
            if character.isspace():
                continue

            normalized_output.append(
                character
            )
            original_positions.append(
                index
            )

        normalized_text = "".join(
            normalized_output
        )

        start = normalized_text.find(
            normalized_placeholder
        )

        if start == -1:
            return None

        end = (
            start
            + len(normalized_placeholder)
        )

        original_start = (
            original_positions[start]
        )

        original_end = (
            original_positions[end - 1]
            + 1
        )

        return (
            original_start,
            original_end,
        )

    def _protect_text(
        self,
        text: str,
        terms: Sequence[str],
    ) -> tuple[str, dict[str, str]]:
        """Replace DNT occurrences with temporary placeholders."""

        spans = find_dnt_spans(
            text,
            terms,
        )

        if not spans:
            return text, {}

        parts: list[str] = []
        mapping: dict[str, str] = {}

        cursor = 0

        for index, (
            start,
            end,
            term,
        ) in enumerate(spans):

            placeholder = self._placeholder(
                index
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
        """
        Restore DNT terms from NLLB output.

        NLLB can insert whitespace inside a placeholder. This method
        detects the placeholder using whitespace-insensitive matching,
        removes the generated placeholder, and inserts the original
        DNT term exactly as supplied by the user.
        """

        if not mapping:
            return text

        result = text

        for placeholder, term in mapping.items():

            span = (
                self._find_generated_placeholder(
                    result,
                    placeholder,
                )
            )

            if span is None:
                raise ValueError(
                    "NLLB modified or removed "
                    "protected DNT terms. "
                    f"Missing: [{term!r}]"
                )

            start, end = span

            result = (
                result[:start]
                + term
                + result[end:]
            )

        return result

    def _generate_batch(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        """Run one NLLB inference batch."""

        if not texts:
            return []

        self.tokenizer.src_lang = source_lang

        forced_bos_token_id = (
            self.tokenizer.convert_tokens_to_ids(
                target_lang
            )
        )

        if forced_bos_token_id is None:
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
            for key, value in encoded.items()
        }

        generation_kwargs = {
            "forced_bos_token_id": (
                forced_bos_token_id
            ),
            "max_new_tokens": (
                self.max_new_tokens
            ),
            "num_beams": self.num_beams,
            "early_stopping": True,
        }

        with torch.inference_mode():

            if self.torch_device.type == "cuda":

                with torch.autocast(
                    device_type="cuda",
                    dtype=torch.float16,
                ):
                    generated = (
                        self.model.generate(
                            **encoded,
                            **generation_kwargs,
                        )
                    )

            else:

                generated = (
                    self.model.generate(
                        **encoded,
                        **generation_kwargs,
                    )
                )

        return list(
            self.tokenizer.batch_decode(
                generated,
                skip_special_tokens=True,
            )
        )

    def _translate_dnt_batch(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
        protected_terms: Sequence[
            Sequence[str]
        ],
    ) -> list[str]:
        """Translate text while preserving DNT terms."""

        protected_texts: list[str] = []
        mappings: list[
            dict[str, str]
        ] = []

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

        if not any(mappings):
            return self._generate_batch(
                texts,
                source_lang,
                target_lang,
            )

        translated = self._generate_batch(
            protected_texts,
            source_lang,
            target_lang,
        )

        if len(translated) != len(texts):
            raise ValueError(
                "NLLB returned an unexpected "
                "number of translations."
            )

        outputs: list[str] = []

        for (
            source,
            translation,
            mapping,
        ) in zip(
            texts,
            translated,
            mappings,
        ):

            restored = self._restore_text(
                translation,
                mapping,
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

    def translate_batch(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
        protected_terms: Sequence[
            Sequence[str]
        ] | None = None,
    ) -> list[str]:
        """
        Translate a sequence of text values.

        When DNT terms are supplied, terms found in each input text
        are protected and restored after NLLB translation.
        """

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

        if protected_terms is None:
            return self._translate_normal_batches(
                texts,
                source_lang,
                target_lang,
            )

        if len(protected_terms) != len(texts):
            raise ValueError(
                "protected_terms must contain "
                "one list per text."
            )

        outputs: list[str] = []

        for text, terms in zip(
            texts,
            protected_terms,
        ):
            actual_terms = normalise_dnt_terms(
                terms
            )

            if not count_dnt_terms(
                text,
                actual_terms,
            ):
                outputs.extend(
                    self._generate_batch(
                        [text],
                        source_lang,
                        target_lang,
                    )
                )
                continue

            outputs.extend(
                self._translate_dnt_batch(
                    [text],
                    source_lang,
                    target_lang,
                    [actual_terms],
                )
            )

        return outputs

    def _translate_normal_batches(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        """Translate text using the configured batch size."""

        outputs: list[str] = []

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