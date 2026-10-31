import logging

from .classifier import classify_ticket
from .groq_ai import analyze_with_groq


def analyze_text(description: str, category_names: list) -> dict:
    """GenAI (Groq) first, ML classifier fallback. Always returns one shape."""
    try:
        result = analyze_with_groq(description, category_names)
        result["engine"] = "genai"
    except Exception:
        logging.exception("Groq analysis failed; using ML classifier")
        result = classify_ticket(description)
        result["engine"] = "ml"
    return result
