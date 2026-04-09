export function checkHasAccount(req) {
  return Boolean(req.user);
}

export function checkAdmin(req) {
  return req.user?.role === 'admin';
}

export function checkCustomer(req) {
  return req.user?.role === 'customer';
}