import { createClient } from '@supabase/supabase-js';

/** The one Supabase client this app has - there is no server, so there is no separate server/browser split the way the Next.js and Remix stacks need. */
export const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_ANON_KEY);
