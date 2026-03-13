import json
import os
import time
from pathlib import Path
from typing import Optional

import anthropic
from openai import AsyncOpenAI

from app.llm.schemas import LLMExtractionResult, LLMExtractionMetadata
from app.config import settings


# Prompt directory
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Cost per 1M tokens (INR) — configurable
COST_RATES = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "gpt-4o-mini": {"input": 1.20, "output": 6.00},
}

# Doc type to prompt file mapping
DOC_TYPE_PROMPT_MAP = {
    "rc_book": "rc_book",
    "driving_license": "driving_license",
    "aadhaar": "aadhaar",
}


class LLMExtractor:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.LLM_PROVIDER

    def _load_prompt(self, document_type: str, version: str = "v1") -> str:
        prompt_name = DOC_TYPE_PROMPT_MAP[document_type]
        prompt_path = PROMPTS_DIR / f"{prompt_name}_{version}.txt"
        return prompt_path.read_text()

    def _build_user_prompt(self, ocr_text_front: Optional[str], ocr_text_back: Optional[str], side: str) -> str:
        parts = []
        if side == "front" and ocr_text_front:
            parts.append(f"OCR text from FRONT side:\n---\n{ocr_text_front}\n---")
        elif side == "back" and ocr_text_back:
            parts.append(f"OCR text from BACK side:\n---\n{ocr_text_back}\n---")
        if not parts:
            parts.append("No OCR text available.")
        return "\n\n".join(parts)

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        rates = COST_RATES.get(model, {"input": 0, "output": 0})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    async def extract(
        self,
        ocr_text_front: Optional[str],
        ocr_text_back: Optional[str],
        document_type: str,
        side: str,
        prompt_version: str = "v1",
    ) -> LLMExtractionResult:
        start = time.time()
        system_prompt = self._load_prompt(document_type, prompt_version)
        system_prompt = system_prompt.replace("{side}", side)
        user_prompt = self._build_user_prompt(ocr_text_front, ocr_text_back, side)

        model = (
            settings.LLM_MODEL_ANTHROPIC if self.provider == "anthropic"
            else settings.LLM_MODEL_OPENAI
        )

        # Retry policy: 1 retry with 2s delay on timeout or 5xx. No retry on 4xx or parse failures.
        last_error = None
        for attempt in range(2):
            try:
                if self.provider == "anthropic":
                    extracted, token_in, token_out, raw = await self._call_anthropic(
                        system_prompt, user_prompt, model
                    )
                else:
                    extracted, token_in, token_out, raw = await self._call_openai(
                        system_prompt, user_prompt, model
                    )

                elapsed_ms = int((time.time() - start) * 1000)
                cost = self._calculate_cost(model, token_in, token_out)

                return LLMExtractionResult(
                    extracted_fields=extracted,
                    metadata=LLMExtractionMetadata(
                        llm_provider=self.provider,
                        llm_model=model,
                        extraction_time_ms=elapsed_ms,
                        prompt_version=prompt_version,
                    ),
                    raw_response=raw,
                    system_prompt_used=system_prompt,
                    status="success",
                    token_input=token_in,
                    token_output=token_out,
                    cost_inr=cost,
                )
            except json.JSONDecodeError as e:
                last_error = e
                break  # No retry on parse failures
            except Exception as e:
                last_error = e
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2)
                continue

        elapsed_ms = int((time.time() - start) * 1000)
        return LLMExtractionResult(
            extracted_fields={},
            metadata=LLMExtractionMetadata(
                llm_provider=self.provider,
                llm_model=model,
                extraction_time_ms=elapsed_ms,
                prompt_version=prompt_version,
            ),
            raw_response={},
            system_prompt_used=system_prompt,
            status="failed",
            error_message=str(last_error),
        )

    async def _call_anthropic(self, system_prompt, user_prompt, model):
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        text = response.content[0].text
        extracted = json.loads(text)
        return extracted, response.usage.input_tokens, response.usage.output_tokens, {"text": text}

    async def _call_openai(self, system_prompt, user_prompt, model):
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        response = await client.chat.completions.create(
            model=model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content
        extracted = json.loads(text)
        token_in = response.usage.prompt_tokens
        token_out = response.usage.completion_tokens
        return extracted, token_in, token_out, {"text": text}
