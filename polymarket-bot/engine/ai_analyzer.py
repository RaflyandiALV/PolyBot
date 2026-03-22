"""
AI Analyzer — The core analysis engine.

Sends news + market context to Gemini API for probability estimation.
Supports multiple API keys with automatic rolling/rotation.
Supports MOCK_AI mode for $0 paper trading.
"""

import json
import os
import random
import time
from typing import Dict, Optional

from dotenv import load_dotenv

from utils.logger import get_logger

logger = get_logger(__name__)
load_dotenv()

# Gemini model to use
_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """
Kamu adalah quantitative analyst untuk prediction market. Tugasmu adalah
mengestimasi probabilitas suatu event terjadi berdasarkan berita terbaru
dan data yang diberikan.

Kamu HARUS merespons HANYA dengan JSON valid, tidak ada teks lain,
tidak ada markdown, tidak ada penjelasan di luar JSON.

Format respons yang WAJIB diikuti:
{
  "probability": float,
  "confidence": "LOW" | "MEDIUM" | "HIGH",
  "reasoning": string,
  "key_factors": [string],
  "time_sensitivity": "HOURS" | "DAYS" | "WEEKS"
}

Rules:
- probability harus antara 0.05 dan 0.95 (tidak boleh 0 atau 1)
- confidence HIGH hanya kalau ada bukti kuat dan konsisten
- confidence LOW kalau berita ambigu atau contradictory
- reasoning harus spesifik, bukan generik
- Jangan pernah berikan rekomendasi BUY/SELL — hanya estimasi probabilitas
""".strip()

USER_PROMPT_TEMPLATE = """
MARKET QUESTION: {question}
CURRENT MARKET PRICE (crowd belief): {market_price} ({market_price_pct}%)
BASE RATE (historical): {base_rate} ({base_rate_pct}%)
MARKET CATEGORY: {category}
RESOLVES: {end_date}

RELEVANT NEWS (last 6 hours):
{news_summary}

Berdasarkan informasi di atas, estimasi probabilitas bahwa market ini
akan resolve TRUE (YES). Pertimbangkan base rate historis sebagai prior,
lalu update berdasarkan berita terbaru (Bayesian reasoning).
""".strip()

# Load and prepare multiple keys
_keys_str = os.getenv("GEMINI_API_KEYS", "")
API_KEYS = [k.strip() for k in _keys_str.split(",") if k.strip()]
_current_key_idx = 0


def _get_next_key() -> Optional[str]:
    """Get the next API key in the rotation."""
    global _current_key_idx
    if not API_KEYS:
        return None
    key = API_KEYS[_current_key_idx]
    _current_key_idx = (_current_key_idx + 1) % len(API_KEYS)
    return key


def _mock_response(base_rate: float) -> Dict:
    """Generate mock AI response for paper trading (MOCK_AI=true)."""
    variation = random.uniform(-0.10, 0.10)
    mock_prob = max(0.05, min(0.95, base_rate + variation))

    confidence_options = ["LOW", "MEDIUM", "HIGH"]
    weights = [0.2, 0.5, 0.3]  
    mock_confidence = random.choices(confidence_options, weights=weights, k=1)[0]

    return {
        "probability": round(mock_prob, 4),
        "confidence": mock_confidence,
        "reasoning": f"Mock analysis based on base rate {base_rate:.2f} with random variation.",
        "key_factors": [
            "Mock factor 1: Historical base rate",
            "Mock factor 2: Random variation for simulation",
        ],
        "time_sensitivity": random.choice(["HOURS", "DAYS", "WEEKS"]),
    }


def _parse_response(text: str) -> Optional[Dict]:
    """Parse JSON response. Returns None on invalid response."""
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]).strip()

        # Some LLMs start JSON with ```json, parsing raw first just in case
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        data = json.loads(cleaned)

        required = ["probability", "confidence", "reasoning", "key_factors", "time_sensitivity"]
        for field in required:
            if field not in data:
                logger.warning(f"Missing field '{field}' in AI response")
                return None

        prob = float(data["probability"])
        if not (0.05 <= prob <= 0.95):
            logger.warning(f"Probability {prob} out of range [0.05, 0.95], clamping")
            prob = max(0.05, min(0.95, prob))
            data["probability"] = prob

        if data["confidence"] not in ("LOW", "MEDIUM", "HIGH"):
            logger.warning(f"Invalid confidence '{data['confidence']}', defaulting to MEDIUM")
            data["confidence"] = "MEDIUM"

        return data

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Failed to parse AI response: {e}")
        return None


def analyze(
    question: str,
    market_price: float,
    base_rate: float,
    category: str,
    end_date: str,
    news: list,
) -> Optional[Dict]:
    """Analyze a market using Gemini API (or mock). Includes key rotation."""
    
    mock_ai = os.getenv("MOCK_AI", "true").lower() == "true"

    if mock_ai:
        logger.info(f"[MOCK AI] Analyzing: {question[:60]}...")
        result = _mock_response(base_rate)
        logger.info(f"[MOCK AI] Result: prob={result['probability']:.2f}, "
                     f"conf={result['confidence']}")
        return result

    # --- Real Gemini API call with Key Rotation ---
    if not API_KEYS:
        logger.error("GEMINI_API_KEYS not configured and MOCK_AI is false")
        return None

    news_summary = ""
    if news:
        for i, article in enumerate(news[:10], 1):  # Max 10 articles
            news_summary += f"{i}. [{article.get('source', 'unknown')}] "
            news_summary += f"{article.get('title', 'No title')}\n"
            desc = article.get("description", "")
            if desc:
                news_summary += f"   {desc[:200]}\n"
    else:
        news_summary = "No recent news found for this market."

    user_prompt = USER_PROMPT_TEMPLATE.format(
        question=question,
        market_price=f"{market_price:.2f}",
        market_price_pct=f"{market_price * 100:.1f}",
        base_rate=f"{base_rate:.2f}",
        base_rate_pct=f"{base_rate * 100:.1f}",
        category=category,
        end_date=end_date,
        news_summary=news_summary,
    )

    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

    import google.generativeai as genai

    max_attempts = max(3, len(API_KEYS))  # Try at least 3 times or loop through all keys
    for attempt in range(1, max_attempts + 1):
        api_key = _get_next_key()
        if not api_key:
            return None
            
        genai.configure(api_key=api_key)
        
        # Obfuscate key for logging
        safe_key = f"{api_key[:6]}...{api_key[-4:]}"

        try:
            # We use generation_config to ensure JSON output structure
            model = genai.GenerativeModel(_MODEL)
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                )
            )

            response_text = response.text
            logger.debug(f"Gemini raw response (Key {safe_key}): {response_text[:200]}")

            result = _parse_response(response_text)
            if result:
                logger.info(f"AI Analysis (Key {safe_key}): prob={result['probability']:.2f}, "
                             f"conf={result['confidence']}")
                return result
            else:
                logger.warning(f"Attempt {attempt}: Failed to parse Gemini response with Key {safe_key}")

        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "quota" in err_msg or "exhausted" in err_msg:
                logger.warning(f"Key {safe_key} rate limited/exhausted. Rotating immediately... ({e})")
                time.sleep(1) # Small delay before trying next key
                continue # Try next key immediately
            else:
                wait_time = 2 ** (attempt - 1)
                logger.warning(f"Attempt {attempt}/{max_attempts} failed with Key {safe_key}: {e}. "
                               f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

    logger.error(f"All {max_attempts} attempts failed for: {question[:60]}")
    return None
