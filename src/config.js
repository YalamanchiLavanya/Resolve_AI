/* ===== EDIT THIS FILE: one login email per role =====
Staff (agent, lead, admin) can ONLY sign in with the emails listed here.
Customers can register with any other email. After editing, reset the demo data:
open the browser console and run  localStorage.clear()  then refresh. */
export const SHOW_DEMO = true; // set false to hide the quick-login buttons
export const ACCOUNTS = {
  admin: {
    name: 'Admin', email: 'admin@resolveai.com', pw: 'Admin@123'
  },
  lead: {
    name: 'Anil Sharma', email: 'teamlead@resolveai.com', pw: 'Lead@123'
  },
  agent: {
    name: 'Priya Nair', email: 'agent@resolveai.com', pw: 'Agent@123'
  }, // Network Support agent
  cust: {
    name: 'Asha Rao', email: 'customer@resolveai.com', pw: 'Customer@123'
  },
  a2: { email: 'agent2@resolveai.com', pw: 'Agent@123' }, // Network Support
  a3: { email: 'billing@resolveai.com', pw: 'Agent@123' }, // Billing Team
  a4: { email: 'tech@resolveai.com', pw: 'Agent@123' }, // Technical Support
};

