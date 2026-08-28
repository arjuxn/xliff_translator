from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


@dataclass
class NLLBTranslator:
    model_name: str = "facebook/nllb-200-distilled-600M"

    # "auto" = CUDA if available, otherwise CPU.
    # You can also explicitly use "cuda" or "cpu".
    device: str = "auto"

    max_input_tokens: int = 1024
    max_new_tokens: int = 1024

    batch_size: int = 4

    # Beam search improves translation quality but is slower.
    num_beams: int = 4

    def __post_init__(self):
        # --------------------------------------------------
        # Select device
        # --------------------------------------------------

        if self.device == "auto":
            self.device = (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )

        if self.device.startswith("cuda"):
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "CUDA was requested, but PyTorch cannot "
                    "access a CUDA device.\n\n"
                    "Check:\n"
                    "  torch.cuda.is_available()\n"
                    "and make sure a CUDA-enabled PyTorch "
                    "build is installed."
                )

        self.torch_device = torch.device(
            self.device
        )

        print(
            f"NLLB device: {self.torch_device}"
        )

        # --------------------------------------------------
        # GPU information
        # --------------------------------------------------

        if self.torch_device.type == "cuda":
            gpu_index = (
                self.torch_device.index
                if self.torch_device.index is not None
                else torch.cuda.current_device()
            )

            gpu_name = torch.cuda.get_device_name(
                gpu_index
            )

            print(
                f"CUDA device: {gpu_name}"
            )

            total_memory = (
                torch.cuda.get_device_properties(
                    gpu_index
                ).total_memory
                / (1024 ** 3)
            )

            print(
                f"GPU memory: "
                f"{total_memory:.2f} GB"
            )

        # --------------------------------------------------
        # Model dtype
        # --------------------------------------------------

        if self.torch_device.type == "cuda":
            dtype = torch.float16
        else:
            dtype = torch.float32

        # --------------------------------------------------
        # Load tokenizer
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Load model
        # --------------------------------------------------

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

        # Move model to selected device.
        self.model.to(
            self.torch_device
        )

        self.model.eval()

        # --------------------------------------------------
        # Ready
        # --------------------------------------------------

        print(
            "NLLB model ready."
        )

    def translate_batch(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
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

        if self.batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than 0."
            )

        # --------------------------------------------------
        # Configure NLLB source language
        # --------------------------------------------------

        self.tokenizer.src_lang = source_lang

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

        outputs: list[str] = []

        # --------------------------------------------------
        # Batch translation
        # --------------------------------------------------

        for start in range(
            0,
            len(texts),
            self.batch_size,
        ):
            batch = list(
                texts[
                    start:start + self.batch_size
                ]
            )

            # ----------------------------------------------
            # Tokenize
            # ----------------------------------------------

            enc = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_input_tokens,
            )

            # ----------------------------------------------
            # Move tensors to GPU / CPU
            # ----------------------------------------------

            enc = {
                key: value.to(
                    self.torch_device
                )
                for key, value in enc.items()
            }

            # ----------------------------------------------
            # Generate
            # ----------------------------------------------

            with torch.inference_mode():

                if self.torch_device.type == "cuda":
                    # Mixed precision reduces GPU memory
                    # usage and generally improves inference
                    # speed on NVIDIA GPUs.
                    with torch.autocast(
                        device_type="cuda",
                        dtype=torch.float16,
                    ):
                        generated = self.model.generate(
                            **enc,
                            forced_bos_token_id=forced_bos,
                            max_new_tokens=self.max_new_tokens,
                            num_beams=self.num_beams,
                            early_stopping=True,
                        )

                else:
                    generated = self.model.generate(
                        **enc,
                        forced_bos_token_id=forced_bos,
                        max_new_tokens=self.max_new_tokens,
                        num_beams=self.num_beams,
                        early_stopping=True,
                    )

            # ----------------------------------------------
            # Decode
            # ----------------------------------------------

            decoded = (
                self.tokenizer.batch_decode(
                    generated,
                    skip_special_tokens=True,
                )
            )

            outputs.extend(
                decoded
            )

        # --------------------------------------------------
        # Safety check
        # --------------------------------------------------

        if len(outputs) != len(texts):
            raise RuntimeError(
                "NLLB returned an unexpected number "
                "of translations: "
                f"{len(outputs)} for "
                f"{len(texts)} inputs."
            )

        return outputs