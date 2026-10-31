"""Category + priority classification and similar-ticket retrieval (scikit-learn)."""
import os
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.metrics.pairwise import cosine_similarity

from .synthetic_data import generate, CATEGORIES

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models.joblib")


def _pipe():
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])


def train(save: bool = True, verbose: bool = True):
    df = generate()
    models = {}
    for target in ("category", "priority"):
        X_tr, X_te, y_tr, y_te = train_test_split(
            df["text"], df[target], test_size=0.2, random_state=1, stratify=df[target])
        p = _pipe().fit(X_tr, y_tr)
        if verbose:
            print(f"== {target} ==")
            print(classification_report(y_te, p.predict(X_te)))
        models[target] = p.fit(df["text"], df[target])  # refit on all data
    if save:
        joblib.dump(models, MODEL_PATH)
    return models


_models = None


def get_models():
    global _models
    if _models is None:
        _models = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else train(verbose=False)
    return _models


PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]


def classify(text: str, sentiment_at_risk: bool = False, plan: str | None = None) -> dict:
    m = get_models()
    cat_p = m["category"].predict_proba([text])[0]
    cat = m["category"].classes_[cat_p.argmax()]
    pr_p = m["priority"].predict_proba([text])[0]
    prio = m["priority"].classes_[pr_p.argmax()]
    reasons = [f"ML priority={prio}"]
    # business-rule boosts on top of the ML score
    idx = PRIORITY_ORDER.index(prio)
    if sentiment_at_risk:
        idx = min(idx + 1, 3); reasons.append("angry/at-risk customer (+1)")
    if plan and plan.lower() in ("enterprise", "business", "premium"):
        idx = min(idx + 1, 3); reasons.append(f"{plan} plan (+1)")
    return {
        "category": cat,
        "category_confidence": round(float(cat_p.max()), 3),
        "priority": PRIORITY_ORDER[idx],
        "priority_confidence": round(float(pr_p.max()), 3),
        "priority_reasons": reasons,
        "suggested_team": CATEGORIES[cat]["team"],
    }


class SimilarityIndex:
    """TF-IDF cosine search over past resolved tickets / knowledge-base articles."""

    def __init__(self, docs=None):
        self.docs, self.vec, self.matrix = [], None, None
        if docs:
            self.build(docs)

    def build(self, docs):
        """docs: list of {id, title, text, solution}"""
        self.docs = docs
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vec.fit_transform([f"{d.get('title','')} {d['text']}" for d in docs])

    def query(self, text: str, k: int = 3, min_score: float = 0.1):
        if not self.docs:
            return []
        sims = cosine_similarity(self.vec.transform([text]), self.matrix)[0]
        top = sims.argsort()[::-1][:k]
        return [{**self.docs[i], "score": round(float(sims[i]), 3)} for i in top if sims[i] >= min_score]


SEED_KB = [
    {"id": "KB1", "title": "Router red light / no internet", "text": "no internet router red light LOS blinking connection lost",
     "solution": "Check fibre cable and ONT power. Power-cycle for 30s. If LOS stays red, check area outage status and raise a technician visit."},
    {"id": "KB2", "title": "Slow speed troubleshooting", "text": "slow speed buffering low mbps latency ping evening",
     "solution": "Run a wired speed test, reboot router, move to 5GHz band, check connected devices. Escalate to L2 if wired speed < 70% of plan."},
    {"id": "KB3", "title": "Double charge / billing dispute", "text": "charged twice bill higher extra charges refund overpayment late fee",
     "solution": "Verify invoice and payment gateway log. Duplicate payments are refunded in 5-7 working days. Waive late fee if payment predates due date."},
    {"id": "KB4", "title": "Router keeps rebooting", "text": "router rebooting restarting overheating adapter power ont",
     "solution": "Replace the power adapter, keep the device ventilated, and schedule a hardware swap if reboot continues."},
    {"id": "KB5", "title": "Installation delay", "text": "installation pending technician not visited shift connection new address",
     "solution": "Confirm work order status, reschedule within 24h, and offer one-time compensation for missed appointments."},
    {"id": "KB6", "title": "App login / OTP issue", "text": "login app otp not received password email phone update",
     "solution": "Verify registered number, resend OTP after 2 minutes, and use manual KYC verification if the number changed."},
    {"id": "KB7", "title": "Plan upgrade / cancellation", "text": "upgrade downgrade cancel connection plans ott switch provider",
     "solution": "Share eligible plans, apply retention offer for cancellation requests, and process changes from the next billing cycle."},
]

kb_index = SimilarityIndex(SEED_KB)
