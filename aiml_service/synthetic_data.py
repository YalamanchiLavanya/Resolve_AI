"""Synthetic ticket generator (no real customer data) used to train the ML models."""
import random
import pandas as pd

CATEGORIES = {
    "Billing": {
        "team": "Billing Team",
        "texts": [
            "I was charged twice this month for my broadband plan",
            "My bill is higher than the plan price, please explain the extra charges",
            "Refund for the overpayment has not reached my account",
            "Auto-pay failed but money was deducted from my bank",
            "Need a copy of my last invoice and GST details",
            "Late fee added even though I paid on time",
        ],
        "base_priority": "Medium",
    },
    "Outage": {
        "team": "Network Operations",
        "texts": [
            "No internet since morning, router shows red light",
            "Entire area has no connectivity, neighbours also affected",
            "Internet is completely down, I work from home and need it urgently",
            "Fibre cable cut near our street, connection lost",
            "Broadband not working at all since last night",
            "LOS light blinking on ONT and no network",
        ],
        "base_priority": "High",
    },
    "Slow Speed": {
        "team": "Technical Support L2",
        "texts": [
            "Speed is much lower than my 100 Mbps plan",
            "Internet keeps buffering during video calls",
            "High latency and ping spikes while gaming",
            "Download speed drops every evening",
            "Wifi connected but pages load very slowly",
        ],
        "base_priority": "Medium",
    },
    "Router/Hardware": {
        "team": "Field Technicians",
        "texts": [
            "Router keeps rebooting again and again",
            "Wifi signal is weak in the bedroom, need extender or replacement",
            "Router power adapter is damaged",
            "ONT device is overheating and shutting down",
            "Need router replacement, ethernet port not working",
        ],
        "base_priority": "Medium",
    },
    "Installation": {
        "team": "Field Technicians",
        "texts": [
            "New connection installation is pending for 5 days",
            "Technician did not visit on the scheduled date",
            "Want to shift my connection to a new address",
            "Installation team left cables hanging, need to fix",
        ],
        "base_priority": "Medium",
    },
    "Account": {
        "team": "Customer Care",
        "texts": [
            "Unable to login to the mobile app, OTP not received",
            "Please update my registered email and phone number",
            "Want to change my wifi password and name",
            "How do I check my data usage in the app",
        ],
        "base_priority": "Low",
    },
    "Plan Change": {
        "team": "Sales & Retention",
        "texts": [
            "I want to upgrade to a higher speed plan",
            "Please downgrade my plan, it is too expensive",
            "Want to cancel my connection and move to another provider",
            "Which plans are available with OTT subscriptions",
        ],
        "base_priority": "Low",
    },
}

URGENT = ["urgently", "immediately", "asap", "for the third time", "very urgent"]
ANGRY = ["this is unacceptable", "worst service ever", "I am very frustrated", "fed up with this"]
PREFIX = ["", "Hello, ", "Hi team, ", "Dear support, ", "Please help. "]


def generate(n: int = 1800, seed: int = 42) -> pd.DataFrame:
    rnd = random.Random(seed)
    rows = []
    for _ in range(n):
        cat = rnd.choice(list(CATEGORIES))
        info = CATEGORIES[cat]
        text = rnd.choice(PREFIX) + rnd.choice(info["texts"])
        prio = info["base_priority"]
        r = rnd.random()
        if r < 0.2:
            text += ", " + rnd.choice(URGENT)
            prio = "High" if prio != "High" else "High"
        elif r < 0.35:
            text += ". " + rnd.choice(ANGRY)
            prio = {"Low": "Medium", "Medium": "High", "High": "High"}[prio]
        elif r < 0.45 and prio == "High":
            pass
        elif r < 0.55 and prio == "Medium":
            prio = "Low"
        rows.append({"text": text, "category": cat, "priority": prio, "team": info["team"]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate()
    df.to_csv("synthetic_tickets.csv", index=False)
    print(df.head(), len(df))
