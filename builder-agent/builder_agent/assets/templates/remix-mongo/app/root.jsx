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

export const meta = () => [
  { title: 'Application' },
  { name: 'description', content: 'Replace this metadata with the application\u2019s own.' },
];

/**
 * The document, and the only place the stylesheet is imported.
 *
 * `Meta` and `Links` are what put a route's own title and stylesheets into
 * `<head>`; `Scripts` is what makes the page interactive. A document missing
 * `Scripts` renders and then does nothing, which reads as a broken component
 * rather than a missing tag.
 */
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

/**
 * One error boundary for the whole application.
 *
 * Remix renders this inside `Layout`, so a thrown error still produces a
 * complete document. Without it the framework's default page appears, which
 * says nothing the user can act on.
 */
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
