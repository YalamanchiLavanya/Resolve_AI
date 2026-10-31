"""Outage pattern spotting: spikes of outage-like tickets per pin code in a rolling window (pandas)."""
import pandas as pd

OUTAGE_WORDS = ["no internet", "down", "not working", "no connectivity", "connection lost", "los", "red light",
                "no network", "fibre cut", "cable cut"]


def detect(tickets: list[dict], window_minutes: int = 60, threshold: int = 5, now: str | None = None) -> list[dict]:
    """tickets: [{id, text, pin_code, created_at(ISO), category?}] -> list of outage alerts."""
    if not tickets:
        return []
    df = pd.DataFrame(tickets)
    df["created_at"] = pd.to_datetime(df["created_at"])
    end = pd.to_datetime(now) if now else df["created_at"].max()
    df = df[df["created_at"] >= end - pd.Timedelta(minutes=window_minutes)]
    low = df["text"].str.lower()
    is_out = low.apply(lambda s: any(w in s for w in OUTAGE_WORDS))
    if "category" in df:
        is_out = is_out | df["category"].isin(["Outage"])
    df = df[is_out]
    alerts = []
    for pin, g in df.groupby("pin_code"):
        n = len(g)
        if n >= threshold:
            alerts.append({
                "pin_code": pin, "ticket_count": n, "ticket_ids": g["id"].tolist(),
                "first_seen": g["created_at"].min().isoformat(), "last_seen": g["created_at"].max().isoformat(),
                "severity": "Critical" if n >= threshold * 3 else "High" if n >= threshold * 2 else "Medium",
                "message": f"Possible outage in {pin}: {n} outage tickets in {window_minutes} min. "
                           "Auto-link tickets, notify team lead, publish a status banner.",
            })
    return sorted(alerts, key=lambda a: -a["ticket_count"])
