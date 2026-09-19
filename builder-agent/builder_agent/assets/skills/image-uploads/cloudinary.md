# Cloudinary

Read this only when Cloudinary was chosen. SKILL.md still governs what is
validated and what is stored; this is Cloudinary's own part.

`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET` are in
`.env.local`. The secret is server-only and never reaches a bundle.

```js
import { v2 as cloudinary } from 'cloudinary'

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
})
```

## Uploading

The file arrives at your route, you check it, and you hand the bytes to
Cloudinary. Let it generate the `public_id`; a client-supplied filename is a
path waiting to be traversed.

```js
const result = await new Promise((resolve, reject) => {
  const stream = cloudinary.uploader.upload_stream(
    { folder: 'listings', resource_type: 'image' },
    (error, uploaded) => (error ? reject(error) : resolve(uploaded)))
  stream.end(buffer)
})

await Photos.create({
  publicId: result.public_id,     // how you delete or transform it later
  url: result.secure_url,         // always the https one
  width: result.width,
  height: result.height,
  format: result.format,
  bytes: result.bytes,
  ownerId: session.userId,
  alt,
})
```

`secure_url`, not `url`: the plain one is http and will be blocked as mixed
content on any https page.

## Asking for the size you actually render

Store the original and transform at render time. Shipping a 4000px original
into a 320px thumbnail is the single most common waste in an app that has
images at all.

```js
cloudinary.url(photo.publicId, {
  width: 640, crop: 'fill', quality: 'auto', fetch_format: 'auto',
})
```

`quality: 'auto'` and `fetch_format: 'auto'` let Cloudinary pick the codec the
requesting browser supports — usually WebP or AVIF — for a fraction of the
bytes and no work from you.

## Deleting

Removing the record without destroying the asset fills the account with files
nobody can find, because the `public_id` that identified them has gone.

```js
await cloudinary.uploader.destroy(photo.publicId)
```

If the destroy fails, keep the record and mark it for retry. Deleting the row
first is how a file becomes permanently unreachable.

## Testing it

Stub the SDK in unit tests — an upload test that reaches Cloudinary is slow,
needs a network, and leaves files behind. Assert that oversized and non-image
files are rejected before the SDK is called at all, that an anonymous request
never reaches it, and that deleting a record calls `destroy` with the right
`public_id`.

- https://cloudinary.com/documentation/node_image_and_video_upload
- https://cloudinary.com/documentation/image_optimization
