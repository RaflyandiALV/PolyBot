"""
Base Rate Module — Step 0 of the integrated framework.

Provides historical prior probabilities per market category,
and keyword-based market classification.
"""

from utils.logger import get_logger

logger = get_logger(__name__)


# Historical base rates per category (hardcoded research data)
BASE_RATES = {
    # Politik
    "politics_incumbent_win":       0.67,
    "politics_challenger_win":      0.33,
    "politics_primary_frontrunner": 0.72,
    "politics_impeachment":         0.08,

    # Ekonomi / Fed
    "fed_rate_cut":                 0.35,
    "fed_rate_hike":                0.25,
    "fed_rate_hold":                0.40,
    "economic_beat_consensus":      0.42,
    "economic_miss_consensus":      0.35,

    # Geopolitik
    "ceasefire_after_negotiation":  0.58,
    "ceasefire_broken":             0.45,
    "sanctions_implemented":        0.62,

    # Crypto
    "btc_breakout_up":              0.45,
    "btc_breakdown_down":           0.35,
    "btc_stays_range":              0.20,
    "crypto_regulation_strict":     0.40,
    "crypto_regulation_lenient":    0.35,

    # Default
    "unknown":                      0.50,
}

# Keyword mapping for classification
_KEYWORD_MAP = {
    # Politik
    "politics_incumbent_win":       ["incumbent", "reelect", "re-elect", "sitting president"],
    "politics_challenger_win":      ["challenger", "opposition", "defeat incumbent"],
    "politics_primary_frontrunner": ["primary", "frontrunner", "nomination", "nominee"],
    "politics_impeachment":         ["impeach", "impeachment", "removal from office"],

    # Ekonomi / Fed
    "fed_rate_cut":                 ["rate cut", "lower rate", "fed cut", "dovish"],
    "fed_rate_hike":                ["rate hike", "raise rate", "fed hike", "hawkish", "tighten"],
    "fed_rate_hold":                ["hold rate", "pause rate", "fed hold", "unchanged rate"],
    "economic_beat_consensus":      ["beat expectation", "beat consensus", "better than expected",
                                     "gdp beat", "jobs beat", "employment beat"],
    "economic_miss_consensus":      ["miss expectation", "miss consensus", "worse than expected",
                                     "gdp miss", "jobs miss", "disappointing"],

    # Geopolitik
    "ceasefire_after_negotiation":  ["ceasefire", "peace deal", "peace agreement", "truce",
                                     "negotiation", "peace talk"],
    "ceasefire_broken":             ["ceasefire broken", "ceasefire violated", "truce broken",
                                     "attack resume"],
    "sanctions_implemented":        ["sanction", "embargo", "trade restriction", "tariff"],

    # Crypto
    "btc_breakout_up":              ["btc", "bitcoin", "breakout", "rally", "surge", "100k",
                                     "all time high", "ath", "bull"],
    "btc_breakdown_down":           ["bitcoin crash", "btc crash", "crypto crash", "bear",
                                     "bitcoin drop", "btc drop"],
    "btc_stays_range":              ["bitcoin range", "btc consolidat", "sideways"],
    "crypto_regulation_strict":     ["crypto ban", "sec crackdown", "crypto regulation strict",
                                     "sec enforcement", "crypto restrict"],
    "crypto_regulation_lenient":    ["crypto friendly", "pro crypto", "crypto regulation lenient",
                                     "crypto adopt", "bitcoin etf approv"],
}


def get_base_rate(category: str) -> float:
    """
    Return base rate for a market category.

    Args:
        category: One of the keys in BASE_RATES.

    Returns:
        Historical probability (0.0 to 1.0). Defaults to 0.50 for unknown.
    """
    rate = BASE_RATES.get(category, BASE_RATES["unknown"])
    logger.debug(f"Base rate for '{category}': {rate}")
    return rate


def classify_market(question: str) -> str:
    """
    Classify a market question to a base rate category using keyword matching.

    Args:
        question: The market question string (e.g. "Will Fed cut rates in March?").

    Returns:
        Category key from BASE_RATES.

    Examples:
        "Will Fed cut rates in March?"     → "fed_rate_cut"
        "Will Ukraine ceasefire hold?"      → "ceasefire_after_negotiation"
        "Will BTC reach $100K?"             → "btc_breakout_up"
    """
    question_lower = question.lower()

    for category, keywords in _KEYWORD_MAP.items():
        for keyword in keywords:
            if keyword in question_lower:
                logger.debug(f"Classified '{question[:60]}...' → {category} (matched: '{keyword}')")
                return category

    logger.debug(f"No category match for '{question[:60]}...' → unknown")
    return "unknown"
