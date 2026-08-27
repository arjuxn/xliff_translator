from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


@dataclass
class NLLBTranslator:
    model_name: str = "facebook/nllb-200-distilled-600M"
    device: str = "auto"
    max_input_tokens: int = 1024
    max_new_tokens: int = 1024
    batch_size: int = 4

    def __post_init__(self):
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_device = torch.device(self.device)
        dtype = torch.float16 if self.torch_device.type == "cuda" else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, use_fast=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name, dtype=dtype)
        self.model.to(self.torch_device)
        self.model.eval()

    def translate_batch(self, texts: Sequence[str], source_lang: str, target_lang: str) -> list[str]:
        if not texts:
            return []
        self.tokenizer.src_lang = source_lang
        forced_bos = self.tokenizer.convert_tokens_to_ids(target_lang)
        outputs: list[str] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start:start + self.batch_size])
            enc = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_input_tokens,
            ).to(self.torch_device)
            with torch.inference_mode():
                generated = self.model.generate(
                    **enc,
                    forced_bos_token_id=forced_bos,
                    max_new_tokens=self.max_new_tokens,
                    num_beams=4,
                )
            outputs.extend(self.tokenizer.batch_decode(generated, skip_special_tokens=True))
        return outputs
