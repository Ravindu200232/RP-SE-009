# Routing

A file under `app/routes/` is a route. The filename is the URL, with three
conventions that decide everything:

| File | URL |
|---|---|
| `_index.jsx` | `/` |
| `about.jsx` | `/about` |
| `blog._index.jsx` | `/blog` |
| `blog.$slug.jsx` | `/blog/anything` |
| `blog.$slug.edit.jsx` | `/blog/anything/edit` |
| `_auth.login.jsx` | `/login`, inside the `_auth` layout |
| `files.$.jsx` | `/files/a/b/c` — a splat |
| `[sitemap.xml].jsx` | `/sitemap.xml` — escaped, so the dot is literal |

- **A dot is a path separator.** `blog.$slug.jsx` is `/blog/:slug`, not a file
  with dots in its name. To put a real dot in a URL, wrap that part in square
  brackets.
- **A leading underscore is a segment that does not appear in the URL.**
  `_index` serves the parent's own path; `_auth.login` puts `/login` inside a
  layout without adding `/auth` to the address.
- **A trailing underscore opts out of the parent layout.**
  `blog_.$slug.jsx` matches `/blog/:slug` but does not render inside
  `blog.jsx`.

A file called `index.jsx` serves `/index`, which is almost never what was
meant. It is `_index.jsx`.

## Nesting

`blog.jsx` and `blog._index.jsx` are a layout and its index. The layout renders
`<Outlet />` where the child goes:

```jsx
import { Outlet } from '@remix-run/react';

export default function BlogLayout() {
  return (
    <section>
      <h1>Blog</h1>
      <Outlet />
    </section>
  );
}
```

Both loaders run, in parallel, on every matching navigation. That is the point
of nesting: the layout's data is not re-fetched by the child and the child does
not wait for it.

A layout with no `<Outlet />` renders itself and then nothing. The child route
matched, its loader ran, and the page is blank — check for the `Outlet` before
suspecting the child.

## Params

```jsx
export async function loader({ params }) {
  const post = await findPost(params.slug);
  if (!post) throw new Response('Not found', { status: 404 });
  return { post };
}
```

`params.slug` comes from `$slug` in the filename. It is a string, always, and
it is user input — validate it before it reaches a query.

## Links

`<Link to="/blog">` from `@remix-run/react`, never a bare `<a>` for an internal
route: an anchor reloads the document and loses the client router. `<NavLink>`
gives you the active state.

- https://remix.run/docs/en/main/file-conventions/routes
