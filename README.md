# ResolveAI – GenAI Service (`genai_service`)

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Set your Groq API key in Windows PowerShell:

```powershell
$env:GROQ_API_KEY="your_key"
```

Get a free API key from [Groq Console](https://console.groq.com/).

Without an API key, the service uses a template-based fallback response.

### 3. Run the Flask application

```bash
python app.py
```

The service runs at:

`http://127.0.0.1:5001`

## Backend Integration

This service uses a Flask Blueprint.

```python
from flask import Flask
from genai_service.router import router

app = Flask(__name__)
app.register_blueprint(router)
```

## API Endpoints

All endpoints use the `/genai` prefix.

### 1. Suggest Reply

**POST** `/genai/suggest-reply`

Request body:

```json
{
  "ticket_text": "My internet is not working.",
  "customer": {
    "name": "Ravi",
    "plan": "Premium"
  },
  "kb_articles": [
    {
      "id": 1,
      "title": "Internet Troubleshooting",
      "solution": "Restart your router and check the internet connection."
    }
  ],
  "sentiment": {
    "sentiment": "negative"
  },
  "tone": "professional"
}
```

Response: Suggested customer reply, response source, and knowledge-base usage information.

### 2. Summarize Ticket

**POST** `/genai/summarize`

Request body:

```json
{
  "history": [
    {
      "role": "customer",
      "message": "My internet is not working."
    },
    {
      "role": "agent",
      "message": "Please restart your router."
    }
  ]
}
```

Response: Ticket conversation summary.

### 3. Customer Satisfaction Report

**POST** `/genai/csat-report`

Request body:

```json
{
  "total_tickets": 100,
  "avg_rating": 3.8,
  "sla_breaches": 8,
  "top_categories": ["Outage", "Billing", "Slow Speed"]
}
```

Response: Weekly customer satisfaction report.

## GenAI Features

1. **Agent Reply Suggestion:** Generates professional customer replies using ticket information and supplied knowledge-base articles.
2. **Ticket Summarization:** Summarizes ticket conversation history.
3. **Customer Satisfaction Report:** Generates weekly CSAT insights.
4. **LLM Fallback:** Uses template-based responses if the LLM is unavailable.

## Safety and Configuration

- Uses environment variables for API keys.
- Uses synthetic ticket data for testing.
- Includes fallback handling when the LLM request fails.
- Reply generation uses supplied knowledge-base information to help avoid unsupported promises about refunds or dates.

## Technology Stack

- Python
- Flask
- Groq API
- Requests
- Large Language Models (LLMs)
