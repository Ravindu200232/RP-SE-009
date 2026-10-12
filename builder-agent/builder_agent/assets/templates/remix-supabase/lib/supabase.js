import { createServerClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr';
import { createClient } from '@supabase/supabase-js';

/** One client per request, built from that request's own cookie header. */
export function supabaseServer(request, headers) {
  return createServerClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY, {
    cookies: {
      getAll: () => parseCookieHeader(request.headers.get('Cookie') ?? ''),
      setAll: (toSet) => {
        for (const { name, value, options } of toSet) {
          headers.append('Set-Cookie', serializeCookieHeader(name, value, options));
        }
      },
    },
  });
}

/** For a Client Component: given the `ENV` a loader passed down (see app/root.jsx), one browser client. */
export function supabaseBrowser(env) {
  return createClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY);
}

/** The service-role key, RLS bypassed entirely. */
export function supabaseAdmin() {
  return createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}
