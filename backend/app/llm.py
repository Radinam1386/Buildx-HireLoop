"""لایهٔ ارتباط با Provider (API سازگار با OpenAI): JSON ساختاریافته + embedding + لاگ توکن."""
import json
import logging
import math
import re
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from .config import S
from .models import Usage

log = logging.getLogger("hireloop.llm")
T = TypeVar("T", bound=BaseModel)

_client: OpenAI | None = None
_json_mode = S.json_mode


class LLMError(Exception):
    pass


def client() -> OpenAI:
    global _client
    if _client is None:
        if not S.base_url or not S.api_key or "REPLACE" in S.base_url + S.api_key:
            raise LLMError("LLM_BASE_URL و LLM_API_KEY در فایل .env تنظیم نشده‌اند.")
        _client = OpenAI(base_url=S.base_url, api_key=S.api_key, timeout=120, max_retries=1)
    return _client


def _log_usage(db: Session, user_id, agent, model, resp):
    try:
        u = getattr(resp, "usage", None)
        db.add(Usage(user_id=user_id, agent=agent, model=model or "",
                     tokens_in=int(getattr(u, "prompt_tokens", 0) or 0),
                     tokens_out=int(getattr(u, "completion_tokens", 0) or 0)))
        db.commit()
    except Exception:  # لاگ نباید جریان اصلی را بشکند
        db.rollback()


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("JSON پیدا نشد")
    return json.loads(text[a:b + 1])


def chat_json(db: Session, user_id, agent: str, model: str, system: str,
              messages: list[dict], schema: type[T], retries: int = 1) -> T:
    """یک فراخوانی LLM با خروجی JSON که با Pydantic اعتبارسنجی می‌شود (با retry)."""
    global _json_mode
    if not model or "REPLACE" in model:
        raise LLMError(f"مدل ایجنت «{agent}» در فایل .env تنظیم نشده است.")
    msgs = [{"role": "system", "content": system}] + messages
    last_err = None
    for attempt in range(retries + 1):
        kwargs = {"model": model, "messages": msgs}
        if _json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if S.reasoning_effort:
            kwargs["extra_body"] = {"reasoning_effort": S.reasoning_effort}
        try:
            resp = client().chat.completions.create(**kwargs)
        except LLMError:
            raise
        except Exception as e:
            if _json_mode and "response_format" in str(e).lower():
                _json_mode = False  # Provider از json_mode پشتیبانی نمی‌کند
                continue
            raise LLMError(f"خطا در ارتباط با مدل: {e}") from e
        _log_usage(db, user_id, agent, model, resp)
        content = (resp.choices[0].message.content or "") if resp.choices else ""
        try:
            return schema.model_validate(_extract_json(content))
        except (ValueError, ValidationError) as e:
            last_err = e
            log.warning("خروجی نامعتبر از %s (تلاش %s): %s", agent, attempt + 1, e)
            msgs = msgs + [{"role": "assistant", "content": content},
                           {"role": "user", "content": "خروجی قبلی JSON معتبر نبود. فقط یک JSON معتبر مطابق ساختار خواسته‌شده بده."}]
    raise LLMError(f"مدل خروجی معتبر نداد: {last_err}")


def embed(texts: list[str]) -> list[list[float]] | None:
    """بردار embedding؛ اگر تنظیم نشده یا خطا بود None (matching با کلیدواژه ادامه می‌یابد)."""
    if not texts or not S.embedding_model or "REPLACE" in S.embedding_model:
        return None
    try:
        r = client().embeddings.create(model=S.embedding_model, input=texts)
        return [d.embedding for d in r.data]
    except Exception as e:
        log.warning("embedding ناموفق: %s", e)
        return None


def cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0
