"""
AI feature 1 - ML ticket classifier (scikit-learn TF-IDF + Logistic Regression)
AI feature 2 - Lexicon sentiment / at-risk scoring

Trained on SYNTHETIC examples only (no real customer data). Used as the
primary engine for category/priority and as the fallback when Groq is down.
"""
import re

CATEGORIES = [
    "Billing Issue", "Slow Speed", "Internet Down / Outage", "Router / Device",
    "Plan Change / Upgrade", "New Installation", "Complaint / Escalation",
]

TRAINING = [
    # Billing Issue
    ("I was charged twice this month", "Billing Issue"),
    ("wrong amount on my invoice please refund", "Billing Issue"),
    ("bill is higher than my plan price", "Billing Issue"),
    ("payment deducted but not updated in my account", "Billing Issue"),
    ("duplicate debit for october recharge", "Billing Issue"),
    ("need refund for extra charges", "Billing Issue"),
    # Slow Speed
    ("internet speed is very slow", "Slow Speed"),
    ("paying for 300 mbps but getting only 20 mbps", "Slow Speed"),
    ("videos keep buffering and downloads are slow", "Slow Speed"),
    ("speed test shows low speed compared to my plan", "Slow Speed"),
    ("lagging during online meetings and gaming", "Slow Speed"),
    ("browsing is slow in the evening", "Slow Speed"),
    # Internet Down / Outage
    ("no internet since morning", "Internet Down / Outage"),
    ("red light on router and no connectivity", "Internet Down / Outage"),
    ("connection is completely down in our area", "Internet Down / Outage"),
    ("LOS light is red please help", "Internet Down / Outage"),
    ("network not working cannot connect at all", "Internet Down / Outage"),
    ("fiber cable cut no signal", "Internet Down / Outage"),
    # Router / Device
    ("wifi keeps disconnecting every few minutes", "Router / Device"),
    ("router keeps restarting", "Router / Device"),
    ("cannot change wifi password on router", "Router / Device"),
    ("ONT device lights are blinking", "Router / Device"),
    ("wifi signal weak in bedroom", "Router / Device"),
    ("router overheating and rebooting", "Router / Device"),
    # Plan Change / Upgrade
    ("I want to upgrade my plan to higher speed", "Plan Change / Upgrade"),
    ("downgrade my plan to a cheaper one", "Plan Change / Upgrade"),
    ("how to renew my broadband plan", "Plan Change / Upgrade"),
    ("change my plan from 100 to 300 mbps", "Plan Change / Upgrade"),
    ("please upgrade my subscription", "Plan Change / Upgrade"),
    # New Installation
    ("I need a new connection at my house", "New Installation"),
    ("shifting to a new address need relocation", "New Installation"),
    ("request installation of fiber in my flat", "New Installation"),
    ("when will the technician come to install", "New Installation"),
    ("moving house please shift my connection", "New Installation"),
    # Complaint / Escalation
    ("I have complained three times and nobody fixes it", "Complaint / Escalation"),
    ("very poor service I want to cancel my connection", "Complaint / Escalation"),
    ("repeated complaints not resolved escalate to manager", "Complaint / Escalation"),
    ("unacceptable support nobody calls me back", "Complaint / Escalation"),
    ("I am switching to another provider because of bad service", "Complaint / Escalation"),
]

CATEGORY_BASE_PRIORITY = {
    "Internet Down / Outage": "HIGH",
    "Complaint / Escalation": "HIGH",
    "Plan Change / Upgrade": "LOW",
    "New Installation": "LOW",
}
ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

CRITICAL_WORDS = ["emergency", "completely down", "all users", "entire area",
                  "whole area", "hospital", "critical", "cancel my connection"]
HIGH_WORDS = ["urgent", "immediately", "asap", "severe", "not working", "no internet"]
LOW_WORDS = ["minor", "occasionally", "sometimes", "when possible"]

ANGRY_WORDS = ["angry", "furious", "unacceptable", "worst", "fed up", "third time",
               "3rd time", "nobody", "cancel my connection", "switching to",
               "useless", "pathetic", "disgusting"]
NEGATIVE_WORDS = ["frustrated", "terrible", "disappointed", "bad", "poor", "slow",
                  "not working", "problem", "issue", "again", "still", "unable",
                  "complained", "complaint"]
POSITIVE_WORDS = ["thank", "thanks", "great", "excellent", "happy", "appreciate",
                  "good", "quick", "polite", "resolved"]

_model = None


def _get_model():
    global _model
    if _model is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline

        texts, labels = zip(*TRAINING)
        _model = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), lowercase=True),
            LogisticRegression(max_iter=1000, C=10),
        )
        _model.fit(texts, labels)
    return _model


def _count(text, words):
    return sum(1 for w in words if w in text)


def analyze_sentiment(text: str):
    """Return (label, score in [-1, 1])."""
    t = text.lower()
    angry = _count(t, ANGRY_WORDS)
    neg = _count(t, NEGATIVE_WORDS)
    pos = _count(t, POSITIVE_WORDS)
    exclaim = min(t.count("!"), 3) * 0.05
    score = max(-1.0, min(1.0, 0.35 * pos - 0.2 * neg - 0.45 * angry - exclaim))
    if (angry >= 1 and score <= -0.4) or score <= -0.7:
        return "ANGRY", round(score, 3)
    if score < -0.15:
        return "NEGATIVE", round(score, 3)
    if score > 0.15:
        return "POSITIVE", round(score, 3)
    return "NEUTRAL", round(score, 3)


def _priority(text: str, category: str) -> str:
    t = text.lower()
    p = CATEGORY_BASE_PRIORITY.get(category, "MEDIUM")
    if _count(t, CRITICAL_WORDS):
        return "CRITICAL"
    if _count(t, HIGH_WORDS):
        p = max(p, "HIGH", key=ORDER.index)
    elif _count(t, LOW_WORDS):
        p = "LOW"
    return p


def classify_ticket(description: str) -> dict:
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Ticket description is required")

    text = re.sub(r"\s+", " ", description.strip())
    model = _get_model()
    probs = model.predict_proba([text])[0]
    best = int(probs.argmax())
    category = str(model.classes_[best])
    sentiment, score = analyze_sentiment(text)

    return {
        "category": category,
        "priority": _priority(text, category),
        "sentiment": sentiment,
        "sentiment_score": score,
        "confidence": round(float(probs[best]) * 100, 2),
        "model_name": "scikit-learn-tfidf-lr",
    }
