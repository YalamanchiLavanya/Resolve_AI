# ResolveAI – AI/ML Flask Service (`aiml_service`)

## Folder structure

```text
aiml_service/
├── app.py
├── requirements.txt
├── README.md
└── aiml_service/
    ├── __init__.py
    ├── ml_models.py
    ├── models.joblib
    ├── outage.py
    ├── router.py
    ├── sentiment.py
    └── synthetic_data.py
```

## Setup (Windows PowerShell)

Run these commands from the outer `aiml_service` folder:

```powershell
python -m pip install -r requirements.txt
```

The supplied `models.joblib` file is loaded automatically. If it is missing, the model is trained from synthetic data automatically on first use. To train it manually:

```powershell
python -c "from aiml_service import ml_models; ml_models.train()"
```

## Run

```powershell
python app.py
```

The service runs at `http://127.0.0.1:8000`.

Open `http://127.0.0.1:8000/` to check that the service is running.

## Backend integration

This service uses Flask Blueprint:

```python
from flask import Flask
from aiml_service.router import router

app = Flask(__name__)
app.register_blueprint(router)
```

## API endpoints

All endpoints use the `/ml` prefix.

### 1. Analyze ticket

**POST** `/ml/analyze-ticket`

```json
{
  "text": "My internet is not working since morning.",
  "customer": {
    "name": "Ravi",
    "plan": "Premium",
    "previous_tickets_30d": 2,
    "escalations": 0
  }
}
```

Returns category, priority, suggested team, sentiment information, and similar knowledge-base articles.

### 2. Sentiment analysis

**POST** `/ml/sentiment`

```json
{
  "text": "This is unacceptable. I am frustrated!",
  "customer": {
    "previous_tickets_30d": 3,
    "escalations": 1
  }
}
```

### 3. Similar tickets / knowledge-base search

**POST** `/ml/similar`

```json
{
  "text": "Router shows red light and internet is down."
}
```

### 4. Detect outages

**POST** `/ml/outages/detect`

```json
{
  "tickets": [
    {
      "id": 1,
      "text": "No internet, router red light",
      "pin_code": "530001",
      "created_at": "2026-10-31T09:00:00"
    }
  ],
  "window_minutes": 60,
  "threshold": 1
}
```

### 5. Reindex knowledge base

**POST** `/ml/kb/reindex`

```json
{
  "docs": [
    {
      "id": "KB1",
      "title": "Internet troubleshooting",
      "text": "No internet router red light connection lost",
      "solution": "Check the fibre cable and restart the router."
    }
  ]
}
```

## AI/ML features

1. Ticket category and priority classification using TF-IDF and Logistic Regression.
2. Suggested team routing.
3. Explainable sentiment and at-risk customer detection.
4. Outage pattern detection by PIN code.
5. Similar knowledge-base retrieval using TF-IDF and cosine similarity.

## Notes

- Uses synthetic training data; do not use real customer data in demos without appropriate safeguards.
- This Flask conversion changes the API layer. The underlying ML, sentiment, outage, and retrieval logic is preserved.
- The `/ml/kb/reindex` endpoint updates the in-memory similarity index; it does not persist the reindexed documents after the process stops.
