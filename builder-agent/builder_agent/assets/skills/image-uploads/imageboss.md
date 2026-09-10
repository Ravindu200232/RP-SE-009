# ImageBoss

Read this only when ImageBoss was chosen. SKILL.md still governs what is
validated and what is stored; this is ImageBoss's own part.

**ImageBoss does not hold your files.** It is a transforming CDN in front of
storage you already own: you upload to your own bucket, and ImageBoss fetches
from it on demand, resizes, and serves the result. So this option has two
halves, and both have to work.

- The app uploads to the bucket, using `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`,
  `STORAGE_SECRET_KEY` and `STORAGE_ENDPOINT`.
- Pages are rendered with an ImageBoss URL built from `IMAGEBOSS_SOURCE` and
  `IMAGEBOSS_BASE_PATH`.

All of them are in `.env.local`.

## The URL

```
https://img.imageboss.me/:source/:operation/:dimensions/:path
```

- `:source` is the source name from the dashboard, exactly as it appears in the
  URL there.
- `:operation` is `cover`, `width`, `height` or `cdn`.
- `:dimensions` is the size — `640x480`, or `800x` for a width with a free
  height. `cdn` takes no dimensions: it serves the original through the CDN.
- `:path` is the object's path **inside the source**, which is relative to the
  base path the source was configured with. A source rooted at `/product` and
  an object at `product/chair.jpg` are addressed as `chair.jpg`.

```js
export function imageUrl(path, { width = 640, operation = 'width' } = {}) {
  const source = process.env.IMAGEBOSS_SOURCE
  const size = operation === 'cdn' ? '' : `/${width}x`
  return `https://img.imageboss.me/${source}/${operation}${size}/${path}`
}
```

Store the object path in MongoDB and build the URL at render time. Storing a
built URL freezes the size into the database, so every future page that wants a
different one has to re-derive it anyway.

## What its errors mean

ImageBoss answers with JSON when something is wrong, and the two messages are
easy to confuse:

- `400 "I don't recognize this account, Boss!"` — the **source name** is wrong.
  Check `IMAGEBOSS_SOURCE` against the dashboard.
- `422 "There is something wrong with your image, Boss! Status: 403 - Access
  denied."` — the source is real, but ImageBoss could not read the object from
  your bucket. Either the credentials the source was given are wrong, the
  bucket name is wrong, or the object is not at that path. This is what a
  freshly created source with placeholder keys returns.

Neither is something the app can fix at run time, so surface them as the
configuration errors they are rather than rendering a broken image.

## Uploading to the bucket

Use the S3-compatible client for whichever provider is behind the source — S3,
R2, Spaces, Wasabi all speak the same API:

```js
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3'

const s3 = new S3Client({
  endpoint: process.env.STORAGE_ENDPOINT,
  credentials: {
    accessKeyId: process.env.STORAGE_ACCESS_KEY,
    secretAccessKey: process.env.STORAGE_SECRET_KEY,
  },
})

const key = `${base}/${crypto.randomUUID()}.${extension}`
await s3.send(new PutObjectCommand({
  Bucket: process.env.STORAGE_BUCKET,
  Key: key,
  Body: buffer,
  ContentType: file.type,
}))
```

The key is generated, never taken from the upload. Store the key; it is what
both the delete and the ImageBoss URL are built from.

ImageBoss needs to be able to read the object. If the bucket is private, the
source must have been given credentials that can read it — that is done in the
ImageBoss dashboard, not from the app.

## Testing it

Unit tests assert the URL builder: a known source, operation and path produce
exactly the documented shape, and a path with a leading slash does not produce
a double slash. Stub the S3 client for the upload tests; assert the generated
key never contains anything from the uploaded filename.

- https://imageboss.me/docs
