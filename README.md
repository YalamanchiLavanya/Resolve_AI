# ResolveAI – React Frontend (React + HTML + CSS + JavaScript, Vite)
## Run
    npm install
    npm run dev        # http://localhost:5173
    npm run build      # production build in dist/
Demo logins (password `demo`): see src/config.js.
## Structure
- `src/App.jsx` – all pages and components (login, customer, agent, team lead, admin)
- `src/engine.js` – synthetic data, AI rules (category, priority, sentiment, routing, outage by PIN, KB search), SLA and metrics. Stored in localStorage.
- `src/styles.css` – design system
## Connect your backend
- Set `window.RESOLVEAI_API` in `index.html` (e.g. `http://localhost:8000/api`); "Draft with AI" will POST `/tickets/{id}/suggest` and read `{reply}`, falling back to the built-in template.
- Replace `analyze`, `createTicket` and the `S` store in `engine.js` with FastAPI calls.
## Demo flow
Customer raises "No internet for the last two hours. PIN 530001. Resolve urgently." → auto category, priority, mood, team, outage alert → Agent drafts AI reply, sends, resolves → Customer rates → Admin dashboard and weekly CSAT.
## Role emails
Edit `src/config.js` to set the login email and password for admin, team lead, agent and customer accounts. Staff can only sign in with those emails; customers register with any other email. After changing it, run `localStorage.clear()` in the browser console and refresh. Set `SHOW_DEMO=false` to hide quick-login buttons.
