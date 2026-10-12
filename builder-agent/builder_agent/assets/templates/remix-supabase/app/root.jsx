import { json } from '@remix-run/node';
import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  isRouteErrorResponse,
  useLoaderData,
  useRouteError,
} from '@remix-run/react';

import './tailwind.css';

/** Response headers for every document. */
export const headers = () => {
  const frameAncestors = process.env.FRAME_ANCESTORS?.trim() || "'none'";
  const supabaseUrl = process.env.SUPABASE_URL ?? '';
  const supabaseWs = supabaseUrl.replace(/^https?:/, 'wss:');
  return {
    ...(frameAncestors === "'none'" ? { 'X-Frame-Options': 'DENY' } : {}),
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Content-Security-Policy': [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline' https:",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data: https:",
      `connect-src 'self' ${supabaseUrl} ${supabaseWs}`.trim(),
      `frame-ancestors ${frameAncestors}`,
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
    ].join('; '),
  };
};

export const meta = () => [
  { title: 'Application' },
  { name: 'description', content: 'Replace this metadata with the application\u2019s own.' },
];

/** Only what a browser Supabase client needs (the anon key, not the service-role key) - see lib/supabase.js's supabaseBrowser(). */
export async function loader() {
  return json({ ENV: { SUPABASE_URL: process.env.SUPABASE_URL, SUPABASE_ANON_KEY: process.env.SUPABASE_ANON_KEY } });
}

/** The document, and the only place the stylesheet is imported. */
export function Layout({ children }) {
  const data = useLoaderData();
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <script
          // `ENV` is how a Client Component reaches `lib/supabase.js`'s supabaseBrowser() - the anon key only, never the service-role key.
          dangerouslySetInnerHTML={{ __html: `window.ENV = ${JSON.stringify(data?.ENV ?? {})}` }}
        />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

/** One error boundary for the whole application. */
export function ErrorBoundary() {
  const error = useRouteError();
  const thrown = isRouteErrorResponse(error);
  return (
    <main>
      <h1>{thrown ? `${error.status} ${error.statusText}` : 'Something went wrong'}</h1>
      <p>{thrown ? error.data : 'Replace this boundary with the application\u2019s own.'}</p>
    </main>
  );
}
