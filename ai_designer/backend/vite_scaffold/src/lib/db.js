// Placeholder mock DB - REWRITTEN by the generator with per-project seeds.
const AppDB = {
  init() {},
  getCurrentUser() { try { return JSON.parse(localStorage.getItem('session')); } catch (e) { return null; } },
  login() { return false },
  logout() { localStorage.removeItem('session'); },
  register() {},
  getRecords() { return []; },
  createRecord() {},
  updateRecord() {},
  deleteRecord() {},
};
if (typeof window !== 'undefined') window.AppDB = AppDB;
export default AppDB;
