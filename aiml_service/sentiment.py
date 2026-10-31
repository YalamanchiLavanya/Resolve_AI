"""Angry / at-risk customer detection. Lexicon + behavioural signals (explainable, no API needed)."""
import re

NEG = {"worst": 2, "unacceptable": 2, "useless": 2, "pathetic": 2, "terrible": 2, "frustrated": 1.5,
       "fed up": 2, "angry": 1.5, "disgusted": 2, "horrible": 2, "waste": 1, "ridiculous": 1.5,
       "third time": 2, "again and again": 1.5, "still not": 1.5, "no response": 1.5, "nobody": 1}
CHURN = ["cancel", "switch provider", "move to another provider", "leaving", "port out", "disconnect",
         "consumer court", "legal", "complaint", "social media", "trai"]
POS = ["thanks", "thank you", "appreciate", "great", "resolved"]


def analyze(text: str, previous_tickets_30d: int = 0, escalations: int = 0) -> dict:
    t = text.lower()
    score, signals = 0.0, []
    for w, wt in NEG.items():
        if w in t:
            score += wt; signals.append(w)
    churn_hits = [w for w in CHURN if w in t]
    score += 2.5 * len(churn_hits); signals += churn_hits
    letters = [c for c in text if c.isalpha()]
    caps = sum(c.isupper() for c in letters) / max(len(letters), 1)
    if caps > 0.5 and len(letters) > 15:
        score += 1.5; signals.append("ALL CAPS")
    if len(re.findall(r"!{2,}", text)):
        score += 1; signals.append("!!")
    if previous_tickets_30d >= 3:
        score += 2; signals.append(f"{previous_tickets_30d} tickets in 30 days")
    score += 1.5 * escalations
    if escalations:
        signals.append(f"{escalations} past escalations")
    score -= sum(1 for w in POS if w in t)
    anger = round(max(0.0, min(score / 8.0, 1.0)), 2)
    label = "angry" if anger >= 0.5 else "frustrated" if anger >= 0.25 else "neutral"
    return {"anger_score": anger, "sentiment": label,
            "at_risk": anger >= 0.5 or bool(churn_hits), "churn_intent": bool(churn_hits),
            "signals": signals}
