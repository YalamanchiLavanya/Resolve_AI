/* engine.js – the 'brain': data, AI rules, routing, SLA and statistics. No screens here. */
import { ACCOUNTS } from './config.js';
/* ResolveAI frontend – self-contained demo. Data lives in localStorage (synthetic). Swap the `S` store for FastAPI calls when your backend is ready. */
export const K = 'resolveai.v2';
/* ResolveAI frontend – self-contained demo. Data lives in localStorage (synthetic). Swap the `S` store for FastAPI calls when your backend is ready. */
export const H = 36e5;
/* ResolveAI frontend – self-contained demo. Data lives in localStorage (synthetic). Swap the `S` store for FastAPI calls when your backend is ready. */
export const now = () => Date.now();
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
  export const dur = ms => {
    const m = Math.max(0, Math.round(ms / 6e4));
    return m >= 60 ? Math.floor(m / 60) + 'h ' + m % 60 + 'm' : m + 'm';
  };
  export const ago = t => dur(now() - t) + ' ago';
  export const when = t => new Date(t).toLocaleString([], {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  });
  export const SLA0 = {
    Critical: 1,
    High: 4,
    Medium: 12,
    Low: 24
  };
  // seed = creates the starting demo users, tickets, teams, SLA hours and knowledge base.
  export function seed() {
    const U = (id, name, role, x = {}) => ({
      id,
      name,
      role,
      email: id + '@demo.com',
      pw: 'demo',
      ...x
    });
    const users = [
      U('cust', 'Asha Rao', 'customer', {
        pin: '530001',
        plan: 'Fiber 100 Mbps',
        area: 'MVP Colony'
      }),
      U('c2', 'Ravi Kumar', 'customer', { pin: '530001', plan: 'Fiber 300 Mbps' }),
      U('c3', 'Sneha Reddy', 'customer', { pin: '530001', plan: 'Fiber 50 Mbps' }),
      U('c4', 'Imran Shaik', 'customer', { pin: '530002', plan: 'Fiber 200 Mbps' }),
      U('agent', 'Priya Nair', 'agent', { team: 'Network Support' }),
      U('a2', 'Kiran Varma', 'agent', { team: 'Network Support' }),
      U('a3', 'Meera Das', 'agent', { team: 'Billing Team' }),
      U('a4', 'Sam Joseph', 'agent', { team: 'Technical Support' }),
      U('lead', 'Anil Sharma', 'lead'),
      U('admin', 'Admin', 'admin')
    ];
    const T = (i, c, pin, text, cat, pri, sent, team, ag, st, h, rate) => {
      const cr = now() - h * H;
      return {
        id: 1000 + i,
        cust: c,
        pin,
        text,
        cat,
        pri,
        sent,
        team,
        agent: ag,
        status: st,
        created: cr,
        due: cr + SLA0[pri] * H,
        msgs: [],
        rating: rate || null,
        esc: false,
        resolvedAt: st === 'Resolved' ? cr + Math.min(SLA0[pri] * H * .8, 3 * H) : null
      };
    };
    const tickets = [
      T(1, 'c2', '530001', 'No internet since morning, router shows red light.', 'Connectivity', 'Critical', 'Negative', 'Network Support', 'agent', 'Open', 1.2),
      T(2, 'c3', '530001', 'Internet is not working in our lane at all.', 'Connectivity', 'Critical', 'Neutral', 'Network Support', 'a2', 'In Progress', .8),
      T(3, 'c4', '530002', 'My speed is very slow during evenings.', 'Speed', 'High', 'Neutral', 'Network Support', 'a2', 'Resolved', 30, 5),
      T(4, 'cust', '530001', 'Charged twice on my last bill.', 'Billing', 'Medium', 'Negative', 'Billing Team', 'a3', 'Resolved', 60, 4),
      T(5, 'c2', '530001', 'Connection disconnects every 10 minutes.', 'Connectivity', 'Medium', 'Neutral', 'Network Support', 'agent', 'Resolved', 90, 5),
      T(6, 'c3', '530001', 'Router keeps rebooting.', 'Hardware', 'High', 'Neutral', 'Technical Support', 'a4', 'Resolved', 120, 3)
    ];
    tickets[0].msgs.push({
      by: 'ravi',
      name: 'Ravi Kumar',
      role: 'customer',
      text: tickets[0].text,
      t: tickets[0].created
    });
    users.forEach(u => {
      const a = ACCOUNTS[u.id];
      if (a)
        Object.assign(u, a);
    });
    return {
      users,
      tickets,
      sla: { ...SLA0 },
      teams: [
        { id: 'Network Support', cats: ['Connectivity', 'Speed'] },
        { id: 'Technical Support', cats: ['Hardware'] },
        { id: 'Billing Team', cats: ['Billing'] },
        { id: 'General Support', cats: ['General'] }
      ],
      kb: [
        {
          id: 1,
          cat: 'Connectivity',
          title: 'Router shows red light / no internet',
          body: 'Check the router power adapter is connected;Restart the router for 30 seconds;Inspect the optical fiber cable for bends or damage;Check for a regional outage in your PIN code;Escalate to the network team if the red light stays on'
        },
        {
          id: 2,
          cat: 'Speed',
          title: 'Slow internet speed',
          body: 'Run a wired speed test near the router;Disconnect unused devices;Move to the 5 GHz Wi-Fi band;Restart the router;Raise a line check if speed stays below 70% of plan'
        },
        {
          id: 3,
          cat: 'Connectivity',
          title: 'Frequent disconnections',
          body: 'Update router firmware;Check cable connectors for loose fittings;Avoid Wi-Fi interference from microwaves and cordless phones;Schedule a line quality test'
        },
        {
          id: 4,
          cat: 'Billing',
          title: 'Duplicate charge on bill',
          body: 'Verify the payment history;Confirm both charges are for the same cycle;Raise a refund request to billing;Refund reaches the account in 5-7 working days'
        },
        {
          id: 5,
          cat: 'Hardware',
          title: 'Router restarts repeatedly',
          body: 'Check the power adapter rating;Try a different socket;Reset router to factory settings;Book a technician visit for replacement'
        }
      ]
    };
  }
  export let S = JSON.parse(localStorage.getItem(K) || 'null') || seed();
  export const save = () => localStorage.setItem(K, JSON.stringify(S));
  export let me = S.users.find(u => u.id === sessionStorage.getItem('me'));
  export const setMe = u => {
    me = u;
  };
  export const user = id => S.users.find(u => u.id === id) || { name: 'Unknown' };
  export const isDone = t => ['Resolved', 'Closed'].includes(t.status);
  export const toast = m => {
    const e = document.getElementById('toast');
    e.textContent = m;
    e.className = 'on';
    clearTimeout(toast.t);
    toast.t = setTimeout(() => e.className = '', 2400);
  };
  /* ---------- AI engine (rules now; replace with ML + LLM) ---------- */
  // analyze = AI rules: reads the complaint text, returns category, priority and sentiment.
  export function analyze(x) {
    x = x.toLowerCase();
    let cat = 'General';
    if (/bill|charge|payment|invoice|refund/.test(x))
      cat = 'Billing';
    else if (/router|red light|modem|\bled\b|hardware|reboot/.test(x))
      cat = 'Hardware';
    else if (/slow|speed|buffer|lag/.test(x))
      cat = 'Speed';
    else if (/internet|connect|disconnect|wifi|wi-fi|outage|network|down/.test(x))
      cat = 'Connectivity';
    let pri = 'Low';
    if (/no internet|not working|unable to access|outage|completely down|no connection|since morning|red light/.test(x) && ['Connectivity', 'Hardware'].includes(cat))
      pri = 'Critical';
    else if (cat === 'Speed' || /urgent|immediately|asap/.test(x))
      pri = 'High';
    else if (cat !== 'General')
      pri = 'Medium';
    const neg = (x.match(/angry|worst|nobody|useless|fed up|terrible|unacceptable|again|still|times|!|immediately|pathetic/g) || []).length;
    const pos = /thank|great|working now|resolved/.test(x);
    return {
      cat,
      pri,
      sent: neg >= 2 || /nobody|fed up|worst/.test(x) ? 'Negative' : pos ? 'Positive' : 'Neutral'
    };
  }
  export const tok = s => [...new Set(s.toLowerCase().match(/[a-z]{4,}/g) || [])];
  // kbMatch = finds the knowledge base articles most similar to the complaint.
  export const kbMatch = (text, cat) => {
    const w = tok(text);
    return S.kb.map(k => ({ k, s: tok(k.title + ' ' + k.body).filter(a => w.includes(a)).length + (k.cat === cat ? 3 : 0) })).filter(x => x.s > 2).sort((a, b) => b.s - a.s).slice(0, 3).map(x => x.k);
  };
  // outages = finds PIN codes with 3+ open connectivity tickets (possible outage).
  export function outages() {
    const m = {};
    S.tickets.filter(t => !isDone(t) && t.cat === 'Connectivity' && now() - t.created < 24 * H).forEach(t => (m[t.pin] = m[t.pin] || []).push(t));
    return Object.entries(m).filter(([, a]) => a.length >= 3).map(([pin, a]) => ({ pin, n: a.length }));
  }
  export const outageFor = t => outages().find(o => o.pin === t.pin && t.cat === 'Connectivity');
  // draft = builds the suggested reply for the agent (template + knowledge base steps).
  export function draft(t) {
    const c = user(t.cust);
    const m = kbMatch(t.text, t.cat)[0];
    const o = outageFor(t);
    const steps = m ? m.body.split(';').map((x, i) => `${i + 1}. ${x.trim()}`).join('\n') : '1. Restart your device.\n2. Check all cables.';
    return `Hi ${c.name.split(' ')[0]},\n\n${t.sent === 'Negative' ? 'I am sorry for the trouble and the wait. ' : 'Thanks for contacting us. '}${o ? `We have several reports from PIN ${t.pin}, so our network team is checking for an area outage. ` : ''}Please try these steps:\n${steps}\n\nIf it is still not fixed, reply here and I will escalate it right away.\n\n${me.name}, ${t.team}`;
  }
  // llm = calls your real AI API if RESOLVEAI_API is set, otherwise uses draft().
  export async function llm(t) {
    if (window.RESOLVEAI_API) {
      try {
        const r = await fetch(window.RESOLVEAI_API + '/tickets/' + t.id + '/suggest', { method: 'POST' });
        if (r.ok)
          return (await r.json()).reply;
      }
      catch (e) {
      }
    }
    return draft(t);
  }
  // pickAgent = smart routing: the team agent with the fewest open tickets.
  export function pickAgent(team) {
    const a = S.users.filter(u => u.role === 'agent' && u.team === team);
    return a.sort((x, y) => S.tickets.filter(t => t.agent === x.id && !isDone(t)).length - S.tickets.filter(t => t.agent === y.id && !isDone(t)).length)[0]?.id || null;
  }
  // createTicket = analyse complaint, choose team and agent, set SLA deadline, save.
  export function createTicket(text, pin, file) {
    const a = analyze(text);
    const team = (S.teams.find(x => x.cats.includes(a.cat)) || S.teams[0]).id;
    const id = Math.max(...S.tickets.map(t => t.id)) + 1;
    const prior = S.tickets.filter(t => t.cust === me.id && now() - t.created < 7 * 24 * H).length;
    const t = {
      id,
      cust: me.id,
      pin,
      text,
      ...a,
      team,
      agent: pickAgent(team),
      status: 'Open',
      created: now(),
      due: now() + S.sla[a.pri] * H,
      msgs: [{
          by: me.id,
          name: me.name,
          role: 'customer',
          text,
          t: now()
        }],
      rating: null,
      esc: false,
      file: file || null,
      repeat: prior >= 2
    };
    if (a.sent === 'Negative' && ['Critical', 'High'].includes(a.pri))
      t.esc = true;
    S.tickets.push(t);
    save();
    return t;
  }
  // slaState = SLA label: time left, overdue, met or breached.
  export const slaState = t => {
    if (isDone(t))
      return (t.resolvedAt || now()) <= t.due ? ['SLA met', 'ok'] : ['SLA breached', 'bad'];
    const r = t.due - now();
    if (r < 0)
      return ['Overdue ' + dur(-r), 'bad'];
    return [dur(r) + ' left', r < S.sla[t.pri] * H * .25 ? 'warn' : 'ok'];
  };
  export const sla = t => {
    const [a, c] = slaState(t);
    return `<span class="b ${c}">${a}</span>`;
  };
  export const pill = (v, c) => `<span class="b ${c || v}">${esc(v)}</span>`;
  /* ---------- metrics ---------- */
  // stats = numbers for the dashboard (totals, average time, satisfaction, SLA %).
  export function stats(list = S.tickets) {
    const d = list.filter(isDone);
    const rated = list.filter(t => t.rating);
    const met = d.filter(t => (t.resolvedAt || 0) <= t.due).length;
    const over = list.filter(t => !isDone(t) && t.due < now()).length;
    return {
      total: list.length,
      open: list.filter(t => !isDone(t)).length,
      res: d.length,
      avg: d.length ? d.reduce((s, t) => s + ((t.resolvedAt || now()) - t.created), 0) / d.length : 0,
      csat: rated.length ? (rated.reduce((s, t) => s + t.rating, 0) / rated.length).toFixed(1) : '–',
      comp: list.length && (d.length + over) ? Math.round(met / (d.length + over) * 100) : 100,
      over,
      neg: list.filter(t => !isDone(t) && t.sent === 'Negative').length
    };
  }
  export const bars = o => {
    const m = Math.max(1, ...Object.values(o));
    return Object.entries(o).map(([k, v]) => `<div class="bar"><span>${esc(k)}</span><div style="width:${v / m * 60}%"></div><em>${v}</em></div>`).join('') || '<p class="mut">No data yet.</p>';
  };
  export const count = (l, f) => l.reduce((o, t) => (o[f(t)] = (o[f(t)] || 0) + 1, o), {});

