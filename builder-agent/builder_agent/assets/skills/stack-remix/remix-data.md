# Loaders, actions and where the database goes

A route's data is its own. `loader` reads, `action` writes, and both run only
on the server.

```jsx
import { json, redirect } from '@remix-run/node';
import { Form, useLoaderData } from '@remix-run/react';

import { connectDb } from '~/lib/db.js';
import { Booking } from '~/models/booking.js';

export async function loader({ params }) {
  await connectDb();
  const booking = await Booking.findById(params.id).lean();
  if (!booking) throw new Response('Not found', { status: 404 });
  return json({ booking });
}

export async function action({ request, params }) {
  await connectDb();
  const form = await request.formData();
  const note = String(form.get('note') ?? '').trim();
  if (!note) return json({ error: 'A note is required.' }, { status: 400 });
  await Booking.updateOne({ _id: params.id }, { $set: { note } });
  return redirect(`/bookings/${params.id}`);
}

export default function BookingRoute() {
  const { booking } = useLoaderData();
  return (
    <Form method="post">
      <input name="note" defaultValue={booking.note} />
      <button type="submit">Save</button>
    </Form>
  );
}
```

## The things that actually go wrong

**What a loader returns has to survive being serialised.** It is sent to the
browser as JSON. A Mongoose document is not JSON: its `_id` is an ObjectId and
its dates are `Date` objects. Use `.lean()` and convert what you send —
`String(doc._id)` — or the client gets `{}` where the id should be and the
failure appears three components away.

**A loader runs on every navigation to that route, including a revalidation
after an action.** It is not a one-time fetch, and it is not cached for you.

**An `action` returning data does not navigate.** `redirect()` is what moves
the browser; returning `json()` re-renders the same route with that data, which
is exactly right for a validation error and wrong for a successful create.

**`request.formData()` can only be read once.** Reading it twice in the same
action gives an empty second read.

**Every form value is a string.** `form.get('quantity')` is `'3'`, and
`form.get('agreed')` is `'on'` or `null`. Convert and validate before it
reaches the database; a checkbox is not a boolean until you make it one.

**A thrown `Response` is a status, a thrown `Error` is a crash.** `throw new
Response(null, { status: 404 })` renders the error boundary as a 404 and is the
right way to say "no such record". Throwing an `Error` is for something that
should never have happened.

## `useFetcher` when you do not want to navigate

`<Form>` navigates. For something that updates in place — marking a row done,
a like button — use `useFetcher`: same server `action`, no route change.

```jsx
const fetcher = useFetcher();
<fetcher.Form method="post" action="/bookings/mark">…</fetcher.Form>
// fetcher.state is 'idle' | 'submitting' | 'loading'
```

`fetcher.state` and `navigation.state` are the loading states. Do not build a
`useState(isLoading)` beside them.

## Never put a secret in a loader's return value

Whatever a loader returns is in the page's HTML. Read the environment in the
loader, use it there, and return only what the page needs to render.

- https://remix.run/docs/en/main/route/loader
- https://remix.run/docs/en/main/route/action
