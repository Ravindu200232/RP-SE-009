# Errors

A route may export an `ErrorBoundary`. Remix renders it in place of that route,
inside its parent layout, so the rest of the page survives.

```jsx
import { isRouteErrorResponse, useRouteError } from '@remix-run/react';

export function ErrorBoundary() {
  const error = useRouteError();

  if (isRouteErrorResponse(error)) {
    // A Response somebody threw on purpose: 404, 403, 400.
    return <p>{error.status} — {error.data}</p>;
  }
  // Something nobody expected.
  return <p>Something went wrong.</p>;
}
```

## The distinction that matters

`isRouteErrorResponse(error)` is true when a `Response` was thrown, and only
then. That is the difference between "this booking does not exist", which is a
normal outcome the page should explain, and "the database connection died",
which is a bug.

Handling them the same way gives a user a stack trace for a typo in a URL, or
gives an operator "Not found" for an outage.

## The boundary has to be able to render

It is the last thing standing. If the `ErrorBoundary` itself depends on
`useLoaderData`, it throws while handling a throw — and that is what produces a
blank page with a console error nobody can trace. A boundary uses only
`useRouteError` and things that cannot fail.

## The root boundary is the floor

`app/root.jsx` exports one, and it renders inside `Layout` so the document is
still complete. Without a root boundary an unhandled error anywhere produces
Remix's own page, which tells the user nothing they can act on.

A route without its own boundary bubbles to the nearest parent that has one.
Put boundaries where a *partial* failure makes sense — a list that could not
load inside a page that is otherwise fine — and let the rest bubble.

## In production the message is not sent

Remix scrubs the error message from the client bundle in production, so
`error.message` is generic there and detailed in development. Log the real one
on the server; do not build a UI that depends on it reaching the browser.

- https://remix.run/docs/en/main/route/error-boundary
- https://remix.run/docs/en/main/guides/errors
