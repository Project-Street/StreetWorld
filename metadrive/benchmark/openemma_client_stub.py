import base64
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

OPENEMMA_ROOT = Path(__file__).resolve().parents[2] / "OpenEMMA"
if str(OPENEMMA_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENEMMA_ROOT))

import torch
from openai import OpenAI
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from qwen_vl_utils import process_vision_info


@dataclass
class OpenEMMAClientConfig:
    model_path: str
    device: str = "cuda:0"
    api_key: Optional[str] = None
    gpt_model: str = "gpt-4o-2024-11-20"


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class OpenEMMAClient:
    def __init__(self, config: OpenEMMAClientConfig) -> None:
        self.config = config
        self.model_path = config.model_path
        self.device = config.device

        if "gpt" in self.model_path.lower():
            self.client = OpenAI(api_key=config.api_key or os.getenv("OPENAI_API_KEY"))
            self.processor = None
            self.model = None
        elif "qwen" in self.model_path.lower():
            self.processor = AutoProcessor.from_pretrained(self.model_path)
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16,
                device_map="auto",
            )
            self.client = None
        else:
            raise ValueError(f"Unsupported model_path: {self.model_path}")

    def infer(self, prompt: str, image_paths: List[str], sys_message: Optional[str] = None) -> str:
        if "gpt" in self.model_path.lower():
            images = [_encode_image(p) for p in image_paths]
            messages = [
                {
                    "role": "user",
                    "content": [
                        *map(lambda x: {"image": x, "resize": 768}, images),
                        prompt,
                    ],
                }
            ]
            if sys_message:
                messages.append({"role": "system", "content": sys_message})
            params = {
                "model": self.config.gpt_model,
                "messages": messages,
                "max_tokens": 400,
            }
            result = self.client.chat.completions.create(**params)
            return result.choices[0].message.content

        content = [{"type": "image", "image": path} for path in image_paths]
        content.append({"type": "text", "text": prompt})
        message = [{"role": "user", "content": content}]
        text = self.processor.apply_chat_template(
            message, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(message)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(self.model.device)
        generated_ids = self.model.generate(**inputs, max_new_tokens=128)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        return output_text[0]
