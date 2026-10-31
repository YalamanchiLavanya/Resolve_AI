# ResolveAI Backend (Flask + MySQL)

Aligned with `DB.sql`. JWT login, role-based access, full ticket workflow, SLA, KB, CSAT, AI + GenAI, admin dashboard.

## Setup
1. Import `DB.sql` into MySQL (event scheduler: `SET GLOBAL event_scheduler = ON;`).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in MySQL + `GROQ_API_KEY`.
4. `python scripts/set_demo_passwords.py` (seed hashes in DB.sql are dummies). Demo password: `Password@123`
5. `python app.py`  (http://localhost:5000)

Demo logins: admin@resolveai.test, lead.tech@resolveai.test, kiran@resolveai.test, ravi@customer.test

Send `Authorization: Bearer <access_token>` on every request except register/login/health.

## Requirement mapping
| Requirement | Where |
|---|---|
| Secure login + RBAC (4 roles) | `routes/auth.py`, `utils/security.py` (`@role_required`), JWT, hashed passwords, audit log |
| Ticket creation: category, priority, attachments | `POST /api/tickets` (JSON or multipart `attachments`), AI fills category/priority unless the customer chooses |
| Assignment + status workflow | `PATCH /<id>/assign`, `POST /<id>/auto-assign`, `PATCH /<id>/status`, `PATCH /<id>/priority` |
| SLA tracking + escalation | DB triggers/procedures + `POST /<id>/escalate`, `/api/dashboard/run-sla-check`, optional APScheduler |
| Knowledge base | `routes/kb.py` (search, CRUD, helpful), FULLTEXT matching on every ticket |
| Customer profiles (plan, connection) | `routes/customers.py` |
| Internal notes + ticket history | `POST/GET /<id>/comments` (`is_internal`), `GET /<id>/history`, customers never see internal items |
| CSAT after closure | `POST /<id>/rating` (resolved/closed tickets only, one per ticket) |
| 2+ AI features | `utils/classifier.py`: (1) TF-IDF + Logistic Regression category/priority, (2) sentiment + at-risk scoring; plus KB FULLTEXT match and outage linking by pincode |
| 2+ GenAI features | `utils/groq_ai.py`: (1) triage analysis at creation, (2) `POST /api/ai/tickets/<id>/draft-reply`, (3) `POST /api/ai/tickets/<id>/summarize` |
| Admin dashboard | `GET /api/dashboard/stats` (SLA compliance, breaches, first-response, resolution time, CSAT, queues, agents, outages, trends) |
| Synthetic data only | DB.sql seed + the synthetic training set in `classifier.py` |

## Roles
- CUSTOMER: own tickets, comments (public), rating, own profile, KB (published).
- SUPPORT_AGENT: assigned tickets (and unassigned in own team), internal notes, status, AI draft/summary.
- TEAM_LEAD: tickets of teams they lead, assign, escalate, dashboard, KB edit.
- ADMIN: everything, user management, KB unpublish, weekly CSAT.
