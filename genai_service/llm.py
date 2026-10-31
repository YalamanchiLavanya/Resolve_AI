
"""GenAI features for ResolveAI.
Uses Groq API when an API key is available.
Falls back to templates when the API is unavailable.
"""

import os
import requests

LLM_URL = os.getenv(
    "LLM_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "llama-3.3-70b-versatile"
)


# Connect to the LLM API
def _llm(system, user, temperature=0.3, max_tokens=500):
    key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")

    if not key:
        print("API key not found. Using template response.")
        return None

    try:
        response = requests.post(
            LLM_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            timeout=25,
            json={
                "model": LLM_MODEL,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ]
            }
        )

        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"].strip()

    except (requests.RequestException, KeyError, IndexError, TypeError) as error:
        print("LLM API error:", error)
        return None


# Instructions for generating customer replies
REPLY_SYSTEM = """
You are a senior broadband support agent assistant.

Rules:
1. Be empathetic and professional.
2. Keep replies within 120 words.
3. Use only the provided knowledge-base information.
4. Never invent refunds, dates or credits.
5. Address the customer by name.
6. End with a clear next step.
7. If the customer is angry or at risk, apologize sincerely
   and offer escalation to a team lead.
"""


# Generate customer reply
def suggest_reply(
    ticket_text,
    customer,
    similar,
    sentiment,
    tone="professional"
):
    customer = customer or {}
    similar = similar or []
    sentiment = sentiment or {}

    context = "\n".join(
        f"- {item.get('title', '')}: {item.get('solution', '')}"
        for item in similar
    ) or "- No matching knowledge-base article."

    prompt = (
        f"Customer: {customer.get('name', 'Customer')}\n"
        f"Plan: {customer.get('plan', 'N/A')}\n"
        f"Sentiment: {sentiment.get('sentiment', 'neutral')}\n"
        f"Tone: {tone}\n"
        f"Ticket: {ticket_text}\n"
        f"Knowledge Base:\n{context}\n\n"
        "Write a professional customer reply."
    )

    output = _llm(REPLY_SYSTEM, prompt)

    source = "llm"

    if not output:
        source = "template"

        steps = (
            similar[0].get("solution")
            if similar else
            "Our team is looking into this and will update you shortly."
        )

        apology = (
            "I am sorry for the trouble this has caused. "
            if sentiment.get("sentiment") != "neutral"
            else ""
        )

        output = (
            f"Hi {customer.get('name', 'there')}, "
            f"{apology}thanks for reaching out. {steps} "
            "Please reply if the issue continues so we can assist you."
        )

    return {
        "suggested_reply": output,
        "source": source,
        "kb_used": [item.get("id") for item in similar]
    }


# Summarize ticket conversation
def summarize_ticket(history):
    history = history or []

    conversation = "\n".join(
        f"{item.get('role', 'Unknown')}: {item.get('message', '')}"
        for item in history
    )

    output = _llm(
        "Summarize this support ticket in 3 bullet points: "
        "issue, steps tried, and next action.",
        conversation,
        max_tokens=250
    )

    if not output:
        if history:
            output = (
                f"Issue: {history[0].get('message', '')[:120]}\n"
                f"Messages so far: {len(history)}\n"
                "Next action: Agent follow-up."
            )
        else:
            output = "No ticket history available."

    return {"summary": output}


# Generate weekly customer satisfaction report
def weekly_csat_report(stats):
    stats = stats or {}

    prompt = str(stats)

    output = _llm(
        "You are a customer experience analyst. "
        "Write a weekly customer satisfaction report with "
        "a headline, 3 insights and 3 recommended actions. "
        "Maximum 180 words.",
        prompt,
        max_tokens=400
    )

    if not output:
        categories = stats.get("top_categories", [])

        output = (
            f"Weekly CSAT: {stats.get('total_tickets', 0)} tickets, "
            f"average rating {stats.get('avg_rating', 'N/A')}/5, "
            f"{stats.get('sla_breaches', 0)} SLA breaches. "
            f"Top categories: {', '.join(categories)}."
        )

    return {"report": output}


# LLM-based category prediction fallback
def classify_with_llm_fallback(text):
    return _llm(
        "Classify the ticket into one category: "
        "Billing, Outage, Slow Speed, Router/Hardware, "
        "Installation, Account, Plan Change. "
        "Return only the category name.",
        text,
        temperature=0,
        max_tokens=10
    )
