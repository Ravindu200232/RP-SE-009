# Supabase Storage

Read this only when Supabase was chosen. SKILL.md still governs what is
validated and what is stored; this is Supabase's own part.

`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_BUCKET` are in
`.env.local`.

**The service role key bypasses row-level security.** It is a server key. It
must never be imported into a client component, inlined into a page, exposed
through a public environment variable, or logged. If the browser needs to talk
to Supabase at all, that is the anon key's job and row-level security's job —
not this one's.

```js
import { createClient } from '@supabase/supabase-js'

// Server only.
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY,
  { auth: { persistSession: false } })
```

## Uploading

The bucket has to exist before the first upload — the app does not create it,
and Supabase returns "Bucket not found" rather than making one. Create it in
Storage → Buckets, and decide there whether it is public.

```js
const path = `${session.userId}/${crypto.randomUUID()}.${extension}`

const { error } = await supabase.storage
  .from(process.env.SUPABASE_BUCKET)
  .upload(path, buffer, { contentType: file.type, upsert: false })

if (error) throw error
```

Two things in that path: it starts with the owner's id, which is what makes a
row-level-security policy expressible later; and the name is generated, not
taken from the upload, which is what stops a filename from being a path.

`upsert: false` means a repeated upload fails instead of silently replacing
somebody's file.

## Getting a URL back

A **public** bucket gives a permanent URL with no round trip:

```js
const { data } = supabase.storage
  .from(process.env.SUPABASE_BUCKET).getPublicUrl(path)
// data.publicUrl
```

A **private** bucket gives a URL that expires, and it has to be minted each
time the page is rendered:

```js
const { data } = await supabase.storage
  .from(process.env.SUPABASE_BUCKET).createSignedUrl(path, 60 * 60)
// data.signedUrl
```

Store the `path` in MongoDB either way — never the signed URL, which is stale
within the hour. Public URLs may be stored as a convenience, but the path is
the thing that identifies the object.

## Resizing

Supabase's image transformation (`transform: { width, quality }` on
`getPublicUrl`) is a paid feature and is not available on the free tier. On the
free tier, resize before upload rather than shipping a 4000px original into a
thumbnail: keep one reasonable original and one thumbnail, both written at
upload time.

## Deleting

```js
await supabase.storage.from(process.env.SUPABASE_BUCKET).remove([photo.path])
```

Remove the object before the record. A record without an object shows a broken
image; an object without a record is invisible and permanent.

## Testing it

Stub the client in unit tests. Assert that the generated path always starts
with the owner's id, that an oversized or non-image file is rejected before the
client is touched, and that deleting a record removes the object it named.

- https://supabase.com/docs/guides/storage/uploads/standard-uploads
- https://supabase.com/docs/guides/storage/serving/downloads
