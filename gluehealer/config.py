"""
GlueHealer configuration.

Loads settings from .env and provides a lightweight LLM client
that calls the OpenRouter API directly via urllib (no native deps).
Includes automatic retry with exponential backoff for rate limits.
"""
import json
import os
import time
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3.5-lightning:free")

# Support Streamlit Community Cloud Secrets (st.secrets)
if not OPENROUTER_API_KEY:
    try:
        import streamlit as _st
        if hasattr(_st, "secrets") and "OPENROUTER_API_KEY" in _st.secrets:
            OPENROUTER_API_KEY = _st.secrets["OPENROUTER_API_KEY"]
        if hasattr(_st, "secrets") and "LLM_MODEL" in _st.secrets and not os.getenv("LLM_MODEL"):
            LLM_MODEL = _st.secrets["LLM_MODEL"]
    except Exception:
        pass

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# --- GlueHealer ---
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
VERSIONS_DIR = os.getenv("VERSIONS_DIR", "job_versions")

# --- AWS Cloud Settings ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", None)
S3_VERSIONS_PREFIX = os.getenv("S3_VERSIONS_PREFIX", "gluehealer-versions")

# --- Retry settings ---
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "2"))
API_RETRY_BASE_DELAY = float(os.getenv("API_RETRY_BASE_DELAY", "2.0"))

# Models to try in order if rate limits or upstream errors occur
FALLBACK_MODELS = [
    LLM_MODEL,
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
]


def chat_completion(messages: list[dict], model: str | None = None) -> str:
    """
    Call the OpenRouter chat completions API and return the assistant
    message content. Uses only stdlib (urllib) — no native DLLs.
    Retries on 429 / network errors with exponential backoff and model fallback.
    """
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY not set. "
            "Copy .env.example to .env and add your key."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/GlueHealer",
        "X-Title": "GlueHealer",
    }

    models_to_try = [model] if model else [m for i, m in enumerate(FALLBACK_MODELS) if m not in FALLBACK_MODELS[:i]]

    last_error = None
    for current_model in models_to_try:
        payload = json.dumps({
            "model": current_model,
            "messages": messages,
            "max_tokens": MAX_TOKENS,
        }).encode("utf-8")

        for attempt in range(1, API_MAX_RETRIES + 1):
            req = urllib.request.Request(
                OPENROUTER_URL,
                data=payload,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode("utf-8"))

                if "choices" in body and body["choices"]:
                    msg = body["choices"][0]["message"]
                    content = msg.get("content")
                    if not content and msg.get("reasoning"):
                        content = msg.get("reasoning")
                    if content:
                        return content
                elif "error" in body:
                    raise RuntimeError(f"OpenRouter returned error: {body['error']}")
                else:
                    raise RuntimeError(f"Unexpected response format: {body}")

            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="replace")
                last_error = e

                if e.code == 429:
                    delay = API_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    print(
                        f"   ⏳ Model '{current_model}' rate limited (429). "
                        f"Retrying in {delay:.0f}s (attempt {attempt}/{API_MAX_RETRIES})..."
                    )
                    time.sleep(delay)
                    continue

                # If 400 or other fatal error for this model, break inner loop and try fallback model
                print(f"   ⚠️ Model '{current_model}' HTTP error {e.code}: {error_body[:200]}")
                break

            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_error = e
                delay = API_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(
                    f"   ⏳ Network/timeout error ({e}). "
                    f"Retrying in {delay:.0f}s (attempt {attempt}/{API_MAX_RETRIES})..."
                )
                time.sleep(delay)
                continue

    raise RuntimeError(
        f"OpenRouter API: all models and retries exhausted. "
        f"Last error: {last_error}"
    )
