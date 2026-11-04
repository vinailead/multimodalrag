"""Production client backed by the official `google-genai` SDK.

Only used by explicit CLI/script runs with `GEMINI_API_KEY`; tests always use the stub.
"""

from __future__ import annotations

from typing import Any

from insurance_mmrag.llm.protocol import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    render_prompt,
)


class GeminiClient:
    def __init__(self, api_key: str, sdk_client: Any | None = None) -> None:
        if sdk_client is None:
            from google import genai

            sdk_client = genai.Client(api_key=api_key)
        self._client: Any = sdk_client

    def generate(self, request: GenerationRequest) -> GenerationResult:
        from google.genai import types

        contents: list[Any] = [render_prompt(request)]
        contents.extend(
            types.Part.from_bytes(data=img, mime_type="image/png") for img in request.images
        )
        response: Any = self._client.models.generate_content(
            model=request.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=request.response_schema,
            ),
        )
        parsed: Any = response.parsed
        if not isinstance(parsed, request.response_schema):
            parsed = request.response_schema.model_validate_json(str(response.text))
        usage: Any = response.usage_metadata
        return GenerationResult(
            parsed=parsed,
            model=request.model,
            prompt_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            completion_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        )

    def embed(self, texts: list[str], model: str, dim: int) -> EmbeddingResult:
        from google.genai import types

        response: Any = self._client.models.embed_content(
            model=model,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=dim),
        )
        vectors = [[float(v) for v in emb.values] for emb in response.embeddings]
        # The embeddings API does not return usage; estimate ~4 chars/token for FinOps.
        tokens = sum(max(1, len(t) // 4) for t in texts)
        return EmbeddingResult(vectors=vectors, model=model, token_count=tokens)
