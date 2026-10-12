import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  isRouteErrorResponse,
  useRouteError,
} from '@remix-run/react';

import './tailwind.css';

/** Response headers for every document. */
export const headers = () => {
  const frameAncestors = process.env.FRAME_ANCESTORS?.trim() || "'none'";
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
      "connect-src 'self'",
      `frame-ancestors ${frameAncestors}`,
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
    ].join('; '),
  };
};

export const meta = () => [
  { title: 'Application' },
  { name: 'description', content: 'Replace this metadata with the application’s own.' },
];

/** The document, and the only place the stylesheet is imported. */
export function Layout({ children }) {
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
      <p>{thrown ? error.data : 'Replace this boundary with the application’s own.'}</p>
    </main>
  );
}
