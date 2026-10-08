import os
from typing import Any

from paperhub.config import BackendConfig, TranslateConfig
from paperhub.core.models import CostEstimate, TranslateRequest, TranslateResponse
from paperhub.errors import PaperHubError
from paperhub.translate.base import SYSTEM_PROMPT, user_prompt


class APIBackend:
    def __init__(self, name: str, config: BackendConfig, settings: TranslateConfig):
        self.name, self.config, self.settings = name, config, settings

    def estimate_cost(self, tokens: int) -> CostEstimate:
        price = None
        if self.config.input_per_million is not None and self.config.output_per_million is not None:
            base = (
                tokens
                * (self.config.input_per_million + 1.5 * self.config.output_per_million)
                / 1e6
            )
            price = (round(base * 0.7, 6), round(base * 2, 6))
        return CostEstimate(
            input_tokens=tokens, estimated_output_tokens=int(tokens * 1.5), estimated_usd=price
        )

    async def translate(self, req: TranslateRequest) -> TranslateResponse:
        key = os.environ.get(f"{self.name.upper()}_API_KEY")
        if not key:
            raise PaperHubError("E_BACKEND_AUTH", f"未配置 {self.name.upper()}_API_KEY")
        if not self.config.model:
            raise PaperHubError("E_CONFIG", f"请配置 translate.backends.{self.name}.model")
        try:
            if self.name == "openai":
                from openai import AsyncOpenAI

                async with AsyncOpenAI(
                    api_key=key,
                    base_url=self.config.base_url,
                    max_retries=0,
                    timeout=self.settings.timeout,
                ) as client:
                    response = await client.chat.completions.create(
                        model=self.config.model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt(req)},
                        ],
                    )
                    if response.choices[0].finish_reason == "length":
                        raise PaperHubError("E_BACKEND_TRUNCATED", "译文被截断，请减少 chunk_chars")
                    text = response.choices[0].message.content or ""
                    usage: dict[str, Any] = response.usage.model_dump() if response.usage else {}
            elif self.name == "anthropic":
                from anthropic import AsyncAnthropic

                async with AsyncAnthropic(
                    api_key=key,
                    base_url=self.config.base_url,
                    max_retries=0,
                    timeout=self.settings.timeout,
                ) as claude:
                    message = await claude.messages.create(
                        model=self.config.model,
                        max_tokens=8192,
                        system=SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": user_prompt(req)}],
                    )
                    if message.stop_reason == "max_tokens":
                        raise PaperHubError("E_BACKEND_TRUNCATED", "译文被截断，请减少 chunk_chars")
                    text = "".join(block.text for block in message.content if block.type == "text")
                    usage = message.usage.model_dump()
            else:
                raise PaperHubError("E_BACKEND_UNKNOWN", "翻译后端未知 / Unknown backend")
            if not text.strip():
                raise PaperHubError("E_BACKEND_EMPTY", "后端未返回译文 / Empty translation")
            return TranslateResponse(text=text, usage=usage)
        except PaperHubError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = (
                "E_BACKEND_AUTH"
                if status in (401, 403)
                else "E_BACKEND_RATE"
                if status == 429
                else "E_BACKEND_FAILED"
            )
            raise PaperHubError(
                code,
                f"{self.name} 请求失败 / Provider request failed",
                "检查 API Key、模型和网络；服务端未保存响应正文",
            ) from None
