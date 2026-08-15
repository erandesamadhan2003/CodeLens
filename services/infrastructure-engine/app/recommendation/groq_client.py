"""
Groq API client wrapper for the infrastructure recommendation engine.
Uses llama-3.3-70b-versatile for fast, high-quality infrastructure analysis.
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"


def get_groq_client():
    """Returns a Groq client instance, or None if GROQ_API_KEY is not set."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — AI recommendations will be disabled.")
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        logger.error("groq package not installed. Run: pip install groq")
        return None


def call_groq_json(prompt: str, system: str, max_tokens: int = 4096):
    """
    Call the Groq API and parse the JSON response.
    Always returns a tuple: (parsed_dict_or_None, tokens_used_int).
    """
    client = get_groq_client()
    if not client:
        return None, 0

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        logger.info(f"Groq call successful. Tokens used: {tokens_used}")
        return json.loads(raw), tokens_used
    except json.JSONDecodeError as e:
        logger.error(f"Groq returned invalid JSON: {e}")
        return None, 0
    except Exception as e:
        logger.error(f"Groq API call failed: {e}")
        return None, 0
