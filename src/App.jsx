/* App.jsx – every screen of ResolveAI. Read top to bottom: small parts first, App at the bottom. */
import { useState, useReducer, useEffect } from 'react';
import { SHOW_DEMO } from './config.js';
import { S, save, setMe, now, dur, when, user, isDone, toast, analyze, kbMatch, outages, outageFor, llm, createTicket, slaState, stats, count } from './engine.js';
// NAV = the sidebar menu items for each role (key, label).
const NAV = {
  customer: [
    ['tickets', 'My tickets'],
    ['new', 'Raise a ticket'],
    ['help', 'Self-help assistant']
  ],
  agent: [
    ['queue', 'My queue'],
    ['kb', 'Knowledge base']
  ],
  lead: [
    ['overview', 'Overview'],
    ['queue', 'All tickets'],
    ['team', 'Agent workload']
  ],
  admin: [
    ['overview', 'Dashboard'],
    ['queue', 'All tickets'],
    ['kb', 'Knowledge base'],
    ['config', 'Teams & SLA'],
    ['users', 'Users'],
    ['report', 'Weekly CSAT report']
  ]
};
const EMAIL = /^\S+@\S+\.\S+$/;
// Pill = small coloured badge (priority, status, mood).
const Pill = ({ v, c }) => <span className={'b ' + (c || v)}>{v}</span>;
// Sla = badge showing time left or overdue for a ticket.
const Sla = ({ t }) => {
  const [a, c] = slaState(t);
  return <span className={'b ' + c}>{a}</span>;
};
// Bars = simple animated bar chart used on dashboards.
const Bars = ({ o }) => {
  const m = Math.max(1, ...Object.values(o));
  const e = Object.entries(o);
  return e.length ? e.map(([k, v]) => <div className="bar" key={k}>
    <span>{k}</span>
    <div style={{ width: v / m * 60 + '%' }}/>
    <em>{v}</em>
  </div>) : <p className="mut">No data yet.</p>;
};
const Head = ({ t, p, children }) => <div className="top">
  <div>
    <h1>{t}</h1>
    {p && <p>{p}</p>}
  </div>
  {children}
</div>;
const Outage = () => outages().map(o => <div className="alert red" key={o.pin}><b>Possible outage in PIN {o.pin}.</b> {o.n} open connectivity tickets in the last 24 hours. Alert the network team.</div>);
// Count = number that counts up from 0 (dashboard KPI cards).
function Count({ v }) {
  const s = String(v);
  const m = s.match(/^(\d+(?:\.\d+)?)(.*)$/);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!m)
      return;
    const to = +m[1];
    let st = null;
    let r;
    const f = ts => {
      st ??= ts;
      const p = Math.min(1, (ts - st) / 900);
      setN(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1)
        r = requestAnimationFrame(f);
    };
    r = requestAnimationFrame(f);
    return () => cancelAnimationFrame(r);
  }, [s]);
  return m ? (+m[1] % 1 ? n.toFixed(1) : Math.round(n)) + m[2] : s;
}
// Signal = animated network graphic on the login page.
const Signal = () => <svg className="sig" viewBox="0 0 420 300" aria-hidden="true">
  <g className="rings">{[0, 1, 2].map(i => <circle key={i} cx="210" cy="150" r="30" style={{ animationDelay: i * 1.3 + 's' }}/>)}</g>
  {[
    [70, 60],
    [350, 70],
    [80, 240],
    [340, 235],
    [210, 28],
    [392, 160]
  ].map(([x, y], i) => <g key={i}>
    <line x1="210" y1="150" x2={x} y2={y} className="lk"/>
    <circle cx={x} cy={y} r="7" className="nd" style={{ animationDelay: i * .45 + 's' }}/>
    {i < 4 && <circle r="3.5" fill="#ffb84d">
      <animateMotion dur={2.4 + i * .6 + 's'} repeatCount="indefinite" path={`M210 150 L${x} ${y}`}/>
    </circle>}
  </g>)}
  <circle cx="210" cy="150" r="16" className="hub"/>
</svg>;
const Field = ({ l, children }) => <>
  <label>{l}</label>
  {children}
</>;
// Login = sign in / register screen. Checks email+password from config.js.
function Login({ go }) {
  const [mode, setMode] = useState('in');
  const [f, setF] = useState({
    name: '',
    email: '',
    pw: '',
    pin: '',
    plan: 'Fiber 50 Mbps'
  });
  const set = k => e => setF({ ...f, [k]: e.target.value });
  const submit = () => {
    if (mode === 'in') {
      const u = S.users.find(u => u.email === f.email.trim().toLowerCase() && u.pw === f.pw);
      return u ? go(u) : toast('Email or password is incorrect. Use a demo role below.');
    }
    if (f.name.trim().length < 2 || !EMAIL.test(f.email) || f.pw.length < 4 || !/^\d{6}$/.test(f.pin))
      return toast('Enter your name, a valid email, a 4+ character password and a 6-digit PIN.');
    if (S.users.some(u => u.email === f.email.toLowerCase()))
      return toast('That email is already registered.');
    const u = {
      id: 'u' + now(),
      name: f.name.trim(),
      role: 'customer',
      email: f.email.toLowerCase(),
      pw: f.pw,
      pin: f.pin,
      plan: f.plan
    };
    S.users.push(u);
    save();
    go(u);
  };
  return <div className="login">
    <section className="hero">
      <Signal />
      <h1>ResolveAI – Smart Ticket Routing and GenAI Agent Assist Platform for Broadband Support</h1>
      <p>ResolveAI makes customer support simple by understanding complaints, organizing tickets, and connecting each issue to the right support team. It helps teams track every request, find faster solutions, and deliver a smooth, stress-free customer experience.</p>
    </section>
    <section className="fm" onKeyDown={e => e.key === 'Enter' && submit()}>
      <h2>{mode === 'in' ? 'Sign in' : 'Create a customer account'}</h2>
      <div className="tabs" style={{ marginTop: 12 }}>
        <button className={'btn ' + (mode === 'in' ? '' : 'sec')} onClick={() => setMode('in')}>Sign in</button>
        <button className={'btn ' + (mode === 'up' ? '' : 'sec')} onClick={() => setMode('up')}>Register</button>
      </div>
      {mode === 'in' && <p className="mut" style={{ margin: '10px 0 0' }}>Staff: sign in with the work email assigned to you by your admin.</p>}
      {mode === 'up' && <Field l="Full name">
        <input value={f.name} onChange={set('name')}/>
      </Field>}
      <Field l="Email">
        <input type="email" value={f.email} onChange={set('email')}/>
      </Field>
      <Field l="Password">
        <input type="password" value={f.pw} onChange={set('pw')}/>
      </Field>
      {mode === 'up' && <>
        <Field l="PIN code">
          <input maxLength={6} inputMode="numeric" placeholder="530001" value={f.pin} onChange={set('pin')}/>
        </Field>
        <Field l="Plan">
          <select value={f.plan} onChange={set('plan')}>
            <option>Fiber 50 Mbps</option>
            <option>Fiber 100 Mbps</option>
            <option>Fiber 300 Mbps</option>
          </select>
        </Field>
      </>}
      <p>
        <button className="btn" style={{ width: '100%', marginTop: 14 }} onClick={submit}>{mode === 'in' ? 'Sign in' : 'Create account'}</button>
      </p>
      {SHOW_DEMO && <p className="mut" style={{ margin: '18px 0 0' }}>Quick demo login (synthetic data):</p>}
      {SHOW_DEMO && <div className="demo">{[
          ['cust', 'Customer'],
          ['agent', 'Support agent'],
          ['lead', 'Team lead'],
          ['admin', 'Admin']
        ].map(([i, l]) => <button key={i} className="btn sec" onClick={() => go(user(i))}>{l}</button>)}</div>}
    </section>
  </div>;
}
// Table = list of tickets. Click a row to open the ticket.
function Table({ list, cols = true, open }) {
  if (!list.length)
    return <div className="card mut">No tickets here yet.</div>;
  return <div className="card tw">
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Complaint</th>
          {cols && <th>Customer</th>}
          <th>Category</th>
          <th>Priority</th>
          <th>Mood</th>
          <th>Status</th>
          <th>SLA</th>
        </tr>
      </thead>
      <tbody>
      {[...list].sort((a, b) => a.due - b.due).map(t => <tr className="row" key={t.id} onClick={() => open(t.id)}>
            <td>#{t.id}</td>
            <td style={{ maxWidth: 300 }}>{t.text.slice(0, 70)} {t.esc && <span className="b bad">Escalated</span>}</td>
            {cols && <td>
              {user(t.cust).name}
              <br />
              <small className="mut">PIN {t.pin}</small>
            </td>}
            <td>{t.cat}</td>
            <td>
              <Pill v={t.pri}/>
            </td>
            <td>
              <Pill v={t.sent}/>
            </td>
            <td>{t.status}</td>
            <td>
              <Sla t={t}/>
            </td>
          </tr>)}</tbody>
    </table>
  </div>;
}
// Detail = one ticket: chat, AI suggestions, status, escalate, notes, rating.
function Detail({ t, me, c }) {
  const [rp, setRp] = useState('');
  const [nt, setNt] = useState('');
  const [st, setSt] = useState(t.status);
  const [ra, setRa] = useState(t.agent);
  const [stars, setStars] = useState(0);
  const [fb, setFb] = useState('');
  const [busy, setBusy] = useState(false);
  const cu = user(t.cust);
  const staff = me.role !== 'customer';
  const o = outageFor(t);
  const hist = S.tickets.filter(x => x.cust === t.cust && x.id !== t.id);
  const post = (text, internal) => t.msgs.push({
    by: me.id,
    name: me.name,
    role: me.role,
    text,
    t: now(),
    internal
  });
  const done = m => {
    save();
    c.refresh();
    toast(m);
  };
  const send = () => {
    if (!rp.trim())
      return toast('Write a reply first.');
    post(rp.trim());
    if (!staff && t.status === 'Waiting on customer')
      t.status = 'In Progress';
    else if (staff && t.status === 'Open')
      t.status = 'In Progress';
    setRp('');
    done('Reply sent');
  };
  const ai = async () => {
    setBusy(true);
    setRp(await llm(t));
    setBusy(false);
    toast('Draft ready. Review before sending.');
  };
  const rate = () => {
    if (!stars)
      return toast('Pick a star rating.');
    t.rating = stars;
    t.feedback = fb.trim();
    done('Thanks for your feedback');
  };
  const kb = kbMatch(t.text, t.cat);
  return <>
    <Head t={`Ticket #${t.id}`} p={`${cu.name} · ${when(t.created)}`}>
      <button className="btn sec" onClick={() => c.setSel(null)}>← Back</button>
    </Head>
    {staff && o && <div className="alert red"><b>Area outage suspected.</b> {o.n} customers in PIN {o.pin} report connectivity problems. Mention it in your reply.</div>}
    <div className="grid det">
      <div>
        <div className="card">
          <div className="row2">
            <Pill v={t.status} c="Neutral"/>
            <Pill v={t.pri}/>
            <Sla t={t}/>
            {t.esc && <span className="b bad">Escalated</span>}
          </div>
          <p style={{ fontSize: 16, margin: '12px 0' }}>{t.text}</p>
          {t.file && <p className="mut">📎 {t.file}</p>}
          <hr style={{ border: 0, borderTop: '1px solid var(--line)' }}/>
          {t.msgs.filter(m => !m.internal || staff).map((m, i) => <div key={i} className={'msg ' + (m.internal ? 'int' : m.by === me.id ? 'me' : '')}>
            <small>{m.internal && 'Internal note · '}{m.name} · {when(m.t)}</small>
            {m.text}
          </div>)}
          {!(isDone(t) && !staff) && <>
            <textarea value={rp} onChange={e => setRp(e.target.value)} placeholder={staff ? 'Reply to customer…' : 'Add more details…'}/>
            <div className="row2" style={{ marginTop: 8 }}>
              {staff && <button className="btn sec" disabled={busy} onClick={ai}>{busy ? 'Drafting…' : '✦ Draft with AI'}</button>}
              <span className="sp"/>
              <button className="btn" onClick={send}>Send reply</button>
            </div>
          </>}
        </div>
        {!staff && isDone(t) && !t.rating && <div className="card" style={{ marginTop: 12 }}>
          <h3>How did we do?</h3>
          <div className="stars">{[1, 2, 3, 4, 5].map(i => <button key={i} className={i <= stars ? 'on' : ''} aria-label={i + ' stars'} onClick={() => setStars(i)}>★</button>)}</div>
          <textarea value={fb} onChange={e => setFb(e.target.value)} placeholder="Tell us more (optional)"/>
          <p>
            <button className="btn" onClick={rate}>Send rating</button>
          </p>
        </div>}
        {t.rating && !staff && <p className="mut">Your rating: {'★'.repeat(t.rating)} {t.feedback && '· ' + t.feedback}</p>}
      </div>
      <div className="grid" style={{ alignContent: 'start' }}>{staff ? <>
            <div className="card ai">
              <h2>✦ AI assist</h2>
              <div className="row2" style={{ margin: '8px 0' }}>
                <Pill v={t.cat} c="Neutral"/>
                <Pill v={t.pri}/>
                <Pill v={t.sent}/>
                {t.repeat && <span className="b warn">Repeat complaint</span>}
              </div>
              <p className="mut" style={{ margin: '4px 0' }}>Routed to <b>{t.team}</b> · due {when(t.due)}</p>
              <h3 style={{ marginTop: 12 }}>Matching knowledge base articles</h3>
              {kb.length ? kb.map(k => <div className="kb" key={k.id}>
                <b>{k.title}</b>
                <br />
                <small>{k.body.split(';').slice(0, 3).join(' → ')}</small>
              </div>) : <p className="mut">No match. Add an article after you solve this one.</p>}
            </div>
            <div className="card">
              <h3>Customer</h3>
              <p style={{ margin: '6px 0' }}>
                {cu.name}
                <br />
                <span className="mut">{cu.plan} · PIN {t.pin}<br />{hist.length} earlier ticket(s)</span>
              </p>
            </div>
            <div className="card">
              <h3>Actions</h3>
              <Field l="Status">
                <select value={st} onChange={e => setSt(e.target.value)}>{['Open', 'In Progress', 'Waiting on customer', 'Resolved', 'Closed'].map(s => <option key={s}>{s}</option>)}</select>
              </Field>
              <div className="row2" style={{ marginTop: 8 }}>
                <button className="btn sm" onClick={() => {
                    t.status = st;
                    if (isDone(t) && !t.resolvedAt)
                      t.resolvedAt = now();
                    done('Status updated');
                  }}>Update</button>
                <button className="btn sm red" onClick={() => {
                    t.status = 'Resolved';
                    t.resolvedAt = now();
                    post('Marked as resolved. Please rate your experience.');
                    done('Ticket resolved');
                  }}>Resolve</button>
                {(me.role !== 'agent' || !t.esc) && <button className="btn sm sec" onClick={() => {
                    t.esc = true;
                    t.pri = 'Critical';
                    t.due = Math.min(t.due, now() + S.sla.Critical * 36e5);
                    post('Escalated to Critical priority.', true);
                    done('Ticket escalated');
                  }}>Escalate</button>}
              </div>
              {me.role !== 'agent' && <>
                <Field l="Reassign to">
                  <select value={ra} onChange={e => setRa(e.target.value)}>{S.users.filter(u => u.role === 'agent').map(u => <option key={u.id} value={u.id}>{u.name} ({u.team})</option>)}</select>
                </Field>
                <p>
                  <button className="btn sm sec" onClick={() => {
                      const u = user(ra);
                      t.agent = u.id;
                      t.team = u.team;
                      done('Reassigned to ' + u.name);
                    }}>Reassign</button>
                </p>
              </>}
              <Field l="Internal note">
                <textarea style={{ minHeight: 60 }} value={nt} onChange={e => setNt(e.target.value)}/>
              </Field>
              <p>
                <button className="btn sm sec" onClick={() => {
                    if (!nt.trim())
                      return toast('Write a note first.');
                    post(nt.trim(), true);
                    setNt('');
                    done('Note saved');
                  }}>Save note</button>
              </p>
            </div>
          </>
            : <div className="card">
              <h3>Ticket details</h3>
              <p className="mut">Category: {t.cat}<br />Assigned team: {t.team}<br />Agent: {user(t.agent).name}<br />Target: {when(t.due)}</p>
            </div>}</div>
    </div>
  </>;
}
// Help = customer self-help assistant (answers from the knowledge base).
function Help({ me }) {
  const [chat, setChat] = useState([]);
  const [q, setQ] = useState('');
  const ask = () => {
    if (!q.trim())
      return;
    const a = analyze(q);
    const m = kbMatch(q, a.cat)[0];
    setChat([
      ...chat,
      { me: 1, text: q },
      { text: m ? `Try this (${m.title}):\n` + m.body.split(';').map((x, i) => `${i + 1}. ${x.trim()}`).join('\n') + '\n\nStill stuck? Open “Raise a ticket” and we will take it from here.' : 'I could not find a guide for that. Please raise a ticket and an agent will help.' }
    ]);
    setQ('');
  };
  return <>
    <Head t="Self-help assistant" p="Ask a question. If we cannot solve it, we will raise a ticket for you."/>
    <div className="card" style={{ maxWidth: 720 }}>
      {chat.length ? chat.map((m, i) => <div key={i} className={'msg ' + (m.me ? 'me' : '')}>{m.text}</div>) : <p className="mut">Try: “my router shows a red light” or “I was charged twice”.</p>}
      <div className="row2" style={{ marginTop: 12 }}>
        <input style={{ flex: 1 }} value={q} placeholder="Describe your problem" onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()}/>
        <button className="btn" onClick={ask}>Ask</button>
      </div>
    </div>
  </>;
}
// NewTicket = customer form to raise a ticket. AI sets category, priority, team.
function NewTicket({ me, c }) {
  const [tx, setTx] = useState('');
  const [pn, setPn] = useState(me.pin || '');
  const [file, setFile] = useState(null);
  const go = () => {
    if (tx.trim().length < 10)
      return toast('Describe the problem in at least 10 characters.');
    if (!/^\d{6}$/.test(pn))
      return toast('Enter a 6-digit PIN code.');
    const t = createTicket(tx.trim(), pn, file && file.name);
    c.setPg('tickets');
    c.setSel(t.id);
    toast(`Ticket #${t.id} raised · ${t.cat} · ${t.pri} priority → ${t.team}${outageFor(t) ? ' · outage suspected' : ''}`);
  };
  return <>
    <Head t="Raise a ticket" p="Describe the problem. We will categorise and route it instantly."/>
    <div className="card" style={{ maxWidth: 680 }}>
      <Field l="What is happening?">
        <textarea value={tx} onChange={e => setTx(e.target.value)} placeholder="e.g. No internet for the last two hours. Router shows a red light."/>
      </Field>
      <Field l="PIN code">
        <input maxLength={6} inputMode="numeric" value={pn} onChange={e => setPn(e.target.value)}/>
      </Field>
      <Field l="Attachment (optional)">
        <input type="file" onChange={e => setFile(e.target.files[0])}/>
      </Field>
      <p>
        <button className="btn" onClick={go}>Submit ticket</button>
      </p>
    </div>
  </>;
}
// Overview = KPI cards and charts for team lead and admin.
function Overview({ me }) {
  const s = stats();
  const K = ({ b, l }) => <div className="card kpi">
    <b>
      <Count v={b}/>
    </b>
    <span>{l}</span>
  </div>;
  return <>
    <Head t={me.role === 'admin' ? 'Dashboard' : 'Support overview'} p="Live view of queues, SLAs and customer mood."/>
    <Outage />
    <div className="grid g4">
      <K b={s.total} l="Total tickets"/>
      <K b={s.open} l="Open"/>
      <K b={s.res} l="Resolved"/>
      <K b={dur(s.avg)} l="Average resolution"/>
      <K b={s.csat + ' / 5'} l="Customer satisfaction"/>
      <K b={s.comp + '%'} l="SLA compliance"/>
      <K b={s.over} l="Overdue now"/>
      <K b={s.neg} l="Unhappy customers waiting"/>
    </div>
    <div className="grid g2" style={{ marginTop: 14 }}>
      <div className="card">
        <h2>By category</h2>
        <Bars o={count(S.tickets, t => t.cat)}/>
      </div>
      <div className="card">
        <h2>By priority</h2>
        <Bars o={count(S.tickets, t => t.pri)}/>
      </div>
      <div className="card">
        <h2>By team</h2>
        <Bars o={count(S.tickets, t => t.team)}/>
      </div>
    </div>
  </>;
}
// Team = agent workload table (team lead).
const Team = () => <>
  <Head t="Agent workload" p="Open tickets per agent."/>
  <div className="card tw">
    <table>
      <thead>
        <tr>
          <th>Agent</th>
          <th>Team</th>
          <th>Open</th>
          <th>Overdue</th>
          <th>Resolved</th>
        </tr>
      </thead>
      <tbody>{S.users.filter(u => u.role === 'agent').map(u => {
          const l = S.tickets.filter(t => t.agent === u.id);
          return <tr key={u.id}>
            <td>{u.name}</td>
            <td>{u.team}</td>
            <td>{l.filter(t => !isDone(t)).length}</td>
            <td>{l.filter(t => !isDone(t) && t.due < now()).length}</td>
            <td>{l.filter(isDone).length}</td>
          </tr>;
        })}</tbody>
    </table>
  </div>
</>;
// KB = knowledge base: view, add (admin/agent) and delete (admin) articles.
function KB({ me, c }) {
  const [f, setF] = useState({
    t: '',
    c: 'Connectivity',
    b: ''
  });
  const set = k => e => setF({ ...f, [k]: e.target.value });
  return <>
    <Head t="Knowledge base" p="Articles power AI suggestions and the customer assistant."/>
      {me.role !== 'lead' && <div className="card" style={{ marginBottom: 14 }}>
        <h3>Add article</h3>
        <Field l="Title">
          <input value={f.t} onChange={set('t')}/>
        </Field>
        <Field l="Category">
          <select value={f.c} onChange={set('c')}>{['Connectivity', 'Speed', 'Hardware', 'Billing', 'General'].map(x => <option key={x}>{x}</option>)}</select>
        </Field>
        <Field l="Fix steps (separate with semicolons)">
          <textarea value={f.b} onChange={set('b')}/>
        </Field>
        <p>
          <button className="btn" onClick={() => {
              if (!f.t.trim() || !f.b.trim())
                return toast('Add a title and steps.');
              S.kb.push({
                id: now(),
                title: f.t.trim(),
                cat: f.c,
                body: f.b.trim()
              });
              save();
              setF({
                t: '',
                c: 'Connectivity',
                b: ''
              });
              c.refresh();
              toast('Article saved');
            }}>Save article</button>
        </p>
      </div>}
    {S.kb.map(k => <div className="card kb" key={k.id}>
      <div className="row2">
        <b>{k.title}</b>
        <Pill v={k.cat} c="Neutral"/>
        <span className="sp"/>
        {me.role === 'admin' && <button className="btn sm sec" onClick={() => {
            S.kb = S.kb.filter(x => x.id !== k.id);
            save();
            c.refresh();
            toast('Article deleted');
          }}>Delete</button>}
      </div>
      <p className="mut" style={{ margin: '6px 0 0' }}>{k.body.split(';').join(' → ')}</p>
    </div>)}
  </>;
}
// Config = admin edits SLA hours and which team handles which category.
function Config() {
  const [sl, setSl] = useState({ ...S.sla });
  const [tc, setTc] = useState(S.teams.map(t => t.cats.join(', ')));
  return <>
    <Head t="Teams & SLA rules"/>
    <div className="grid g2">
      <div className="card">
        <h2>SLA targets (hours)</h2>
        {Object.keys(sl).map(p => <Field key={p} l={p}>
          <input type="number" min="1" value={sl[p]} onChange={e => setSl({ ...sl, [p]: e.target.value })}/>
        </Field>)}
        <p>
          <button className="btn" onClick={() => {
              for (const p in sl)
                if (!(+sl[p] > 0))
                  return toast('SLA hours must be above 0.');
              for (const p in sl)
                S.sla[p] = +sl[p];
              save();
              toast('SLA rules saved');
            }}>Save SLA rules</button>
        </p>
        <p className="mut">New tickets use the updated targets.</p>
      </div>
      <div className="card">
        <h2>Teams and categories</h2>
        {S.teams.map((t, i) => <Field key={t.id} l={t.id + ' handles'}>
          <input value={tc[i]} onChange={e => setTc(tc.map((x, j) => j === i ? e.target.value : x))}/>
        </Field>)}
        <p>
          <button className="btn" onClick={() => {
              S.teams.forEach((t, i) => t.cats = tc[i].split(',').map(x => x.trim()).filter(Boolean));
              save();
              toast('Routing saved');
            }}>Save routing</button>
        </p>
      </div>
    </div>
  </>;
}
// Users = admin lists users and adds staff.
function Users({ c }) {
  const [f, setF] = useState({
    n: '',
    e: '',
    r: 'agent',
    t: S.teams[0].id
  });
  const set = k => e => setF({ ...f, [k]: e.target.value });
  return <>
    <Head t="Users"/>
    <div className="grid g2">
      <div className="card tw">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Team</th>
            </tr>
          </thead>
          <tbody>{S.users.map(u => <tr key={u.id}>
              <td>{u.name}</td>
              <td>{u.email}</td>
              <td>{u.role}</td>
              <td>{u.team || '–'}</td>
            </tr>)}</tbody>
        </table>
      </div>
      <div className="card">
        <h3>Add staff member</h3>
        <Field l="Name">
          <input value={f.n} onChange={set('n')}/>
        </Field>
        <Field l="Email">
          <input type="email" value={f.e} onChange={set('e')}/>
        </Field>
        <Field l="Role">
          <select value={f.r} onChange={set('r')}>
            <option value="agent">Support agent</option>
            <option value="lead">Team lead</option>
            <option value="admin">Admin</option>
          </select>
        </Field>
        <Field l="Team (agents)">
          <select value={f.t} onChange={set('t')}>{S.teams.map(t => <option key={t.id}>{t.id}</option>)}</select>
        </Field>
        <p>
          <button className="btn" onClick={() => {
              if (!f.n.trim() || !EMAIL.test(f.e))
                return toast('Enter a name and valid email.');
              S.users.push({
                id: 'u' + now(),
                name: f.n.trim(),
                email: f.e.toLowerCase(),
                role: f.r,
                pw: 'demo',
                team: f.r === 'agent' ? f.t : undefined
              });
              save();
              setF({
                ...f,
                n: '',
                e: ''
              });
              c.refresh();
              toast('User added');
            }}>Add user</button>
        </p>
        <p className="mut">Default password: demo</p>
      </div>
    </div>
  </>;
}
// Weekly = weekly customer satisfaction report with CSV download.
function Weekly() {
  const w = S.tickets.filter(t => t.rating && ((t.resolvedAt && now() - t.resolvedAt < 7 * 864e5) || now() - t.created < 8 * 864e5));
  const by = {};
  w.forEach(t => (by[t.team] = by[t.team] || []).push(t.rating));
  const avg = Object.fromEntries(Object.entries(by).map(([k, v]) => [k, +(v.reduce((a, b) => a + b, 0) / v.length).toFixed(1)]));
  const csv = () => {
    const r = ['ticket,team,rating,feedback', ...S.tickets.filter(t => t.rating).map(t => [t.id, t.team, t.rating, '"' + (t.feedback || '').replace(/"/g, '""') + '"'].join(','))].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([r], { type: 'text/csv' }));
    a.download = 'weekly-csat.csv';
    a.click();
  };
  const fbs = S.tickets.filter(t => t.feedback);
  return <>
    <Head t="Weekly customer satisfaction" p="Ratings from the last 7 days.">
      <button className="btn" onClick={csv}>Download CSV</button>
    </Head>
    <div className="grid g2">
      <div className="card">
        <h2>Average rating by team</h2>
        <Bars o={avg}/>
      </div>
      <div className="card">
        <h2>Rating spread</h2>
        <Bars o={count(S.tickets.filter(t => t.rating), t => t.rating + ' stars')}/>
      </div>
    </div>
    <h2 style={{ margin: '18px 0 8px' }}>Recent feedback</h2>
    {fbs.length ? fbs.map(t => <div className="card kb" key={t.id}>{'★'.repeat(t.rating)} · #{t.id} · {t.feedback}</div>) : <p className="mut">No written feedback yet.</p>}
  </>;
}
// App = main component. Decides: login screen, or sidebar + current page.
export default function App() {
  const [, bump] = useReducer(x => x + 1, 0);
  const [me, setU] = useState(() => {
    const u = S.users.find(u => u.id === sessionStorage.getItem('me'));
    setMe(u);
    return u;
  });
  const [pg, setPg] = useState(() => me ? NAV[me.role][0][0] : '');
  const [sel, setSel] = useState(null);
  useEffect(() => {
    const i = setInterval(bump, 6e4);
    return () => clearInterval(i);
  }, []);
  const go = u => {
    setMe(u);
    sessionStorage.setItem('me', u.id);
    setPg(NAV[u.role][0][0]);
    setSel(null);
    setU(u);
  };
  const out = () => {
    setMe(null);
    sessionStorage.clear();
    setU(undefined);
  };
  if (!me)
    return <Login go={go}/>;
  const c = {
    refresh: bump,
    setSel,
    setPg,
    me
  };
  const mine = me.role === 'customer' ? S.tickets.filter(t => t.cust === me.id) : me.role === 'agent' ? S.tickets.filter(t => t.team === me.team) : S.tickets;
  const open = id => setSel(id);
  const V = {
    customer: {
      tickets: () => <>
        <Head t="My tickets" p="Track every complaint and rate the resolution."/>
        <Table list={mine} cols={false} open={open}/>
      </>,
      new: () => <NewTicket me={me} c={c}/>,
      help: () => <Help me={me}/>
    },
    agent: { queue: () => <>
        <Head t="My queue" p={`Tickets for ${me.team}, most urgent first.`}/>
        <Outage />
        <Table list={mine} open={open}/>
      </>, kb: () => <KB me={me} c={c}/> },
    lead: {
      overview: () => <Overview me={me}/>,
      queue: () => <>
        <Head t="All tickets" p="Sorted by SLA deadline."/>
        <Table list={mine} open={open}/>
      </>,
      team: Team
    },
    admin: {
      overview: () => <Overview me={me}/>,
      queue: () => <>
        <Head t="All tickets"/>
        <Table list={mine} open={open}/>
      </>,
      kb: () => <KB me={me} c={c}/>,
      config: Config,
      users: () => <Users c={c}/>,
      report: Weekly
    }
  };
  const View = V[me.role][pg] || Object.values(V[me.role])[0];
  const tk = sel && S.tickets.find(t => t.id === sel);
  return <div className="shell">
    <aside>
      <div className="logo"><span className="bars">
          <i />
          <i />
          <i />
          <i />
        </span>ResolveAI</div>
      {NAV[me.role].map(([k, l]) => <button key={k} className={'nav ' + (pg === k && !sel ? 'on' : '')} onClick={() => {
          setPg(k);
          setSel(null);
        }}>{l}</button>)}
      <div className="who">
        <span className="av">{me.name[0]}</span>
        <b>{me.name}</b>
        {{
          customer: 'Customer',
          agent: 'Agent · ' + me.team,
          lead: 'Team lead',
          admin: 'Administrator'
        }[me.role]}
        <br />
        <button className="btn sec sm" style={{ marginTop: 8 }} onClick={out}>Sign out</button>
      </div>
    </aside>
    <main key={tk ? 't' + tk.id : pg} className="page">{tk ? <Detail key={tk.id} t={tk} me={me} c={c}/> : <View />}</main>
  </div>;
}

