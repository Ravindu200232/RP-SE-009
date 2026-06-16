// Centralized backend-error formatter for the studio.
// Turns ANY error shape into readable text and GUARANTEES it never renders
// "[object Object]". Handles:
//   - a bare string                         "simple string error"
//   - an Error instance                     new Error("boom")          -> "boom"
//   - FastAPI 422 detail array              {detail:[{loc,msg}]}       -> the msg(s)
//   - FastAPI detail string                 {detail:"Something failed"} -> "Something failed"
//   - backend error string                  {error:"Something failed"} -> "Something failed"
//   - backend error object                  {error:{message:"Bad request"}} -> "Bad request"
//   - unknown / nested objects              -> compact JSON (never [object Object])
//   - empty / null / undefined              -> the fallback
export function errText(data, fallback = 'Something went wrong') {
  const pick = (e) => {
    if (e == null) return '';
    if (typeof e === 'string') return e.trim();
    if (e instanceof Error) return e.message || String(e);
    if (typeof e !== 'object') return String(e);
    if (Array.isArray(e)) return e.map(pick).filter(Boolean).join('; ');
    if (typeof e.msg === 'string') return e.msg;          // FastAPI 422 item
    if (typeof e.message === 'string') return e.message;  // Error-like / {message}
    if (e.error != null) return pick(e.error);            // nested {error:...}
    if (e.detail != null) return pick(e.detail);          // nested {detail:...}
    try { return JSON.stringify(e); } catch { return String(e); }
  };
  // Prefer an explicit error/detail field; otherwise treat `data` itself as the error.
  const out = pick(data?.error ?? data?.detail ?? data);
  return out && out !== '[object Object]' && out !== '{}' ? out : fallback;
}

export default errText;
