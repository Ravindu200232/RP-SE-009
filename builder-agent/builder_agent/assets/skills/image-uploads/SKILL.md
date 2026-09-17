---
name: image-uploads
description: Let people upload pictures - the storage the user chose for the file, MongoDB for what the record says about it - including what to validate, what to store, and how to prove it works.
---

# Image uploads

Use this skill when a person puts a picture into the product: a profile photo, a
listing's gallery, a dish, a room, a proof of payment, a document scan. Not for
pictures the build itself generates or ships.

## The file does not go in the database

Two stores, each holding what it is good at: **the file goes to the storage
that was chosen, MongoDB keeps the record.** A base64 image in a Mongo document makes every
query that touches that collection drag megabytes across the wire, blows the
16MB document limit on a handful of photos, and gives you no thumbnail, no
resizing and no CDN. Store the URL and the identifier the storage gave you back;
never the bytes.

The record is the interesting half, and it is yours to design:

```
{ storageId, url, width, height, format, bytes,
  ownerId, uploadedAt, alt, caption }
```

`storageId` is whatever the chosen storage identifies the object by - a
Cloudinary `public_id`, a Supabase path, a bucket key - and it is what lets you
delete or resize it later. `ownerId` is what makes authorisation possible, and
`alt` is what makes the page accessible. A record without `storageId` is an
orphaned file nobody can ever remove.

## What was already settled

Where the pictures go cannot be read out of a repository, so the user was asked
before the plan was written. That answer is in the plan under "already
settled". Do not ask again and do not build a switch that supports all of them:
build the one that was chosen, and read its file and no other.

- **This machine** - files under `public/uploads`, served by the app itself.
  Nothing to read; just do not pretend it survives a redeploy.
- **Cloudinary** - `readSkill("image-uploads", "cloudinary.md")`
- **Supabase Storage** - `readSkill("image-uploads", "supabase.md")`
- **ImageBoss** - `readSkill("image-uploads", "imageboss.md")`

Their settings are already in `.env.local` under the names the question used.
Read them from `process.env`; never write one into source. If nobody answered,
the names are in `.env.example` - build against `process.env` anyway and fail
with a message naming the missing variable rather than uploading into nowhere.

## What has to be true

**Validate on the server, whatever the browser said.** `accept="image/*"` and a
client-side size check are conveniences; the request can be made without a
browser. Check the real content type and the real size on the server, and
accept an explicit list of formats rather than rejecting a list of bad ones.

**An upload is an authenticated action.** Anonymous upload is a free file host
for whoever finds it. Require a session, and record who uploaded what.

**Bound the size before you read the body.** Set the framework's body limit and
reject an oversized request rather than buffering it into memory first.

**Never trust a filename.** It arrives from the client and may contain a path.
Let the storage generate the identifier, or generate one yourself; never
concatenate the uploaded name into a path or a key.

**Deleting the record deletes the file.** Removing the document and leaving the
object behind fills the account with files nobody can find, because the
identifier that named them has gone. Delete the object first; if that fails,
keep the record so it can be retried rather than losing the reference.

**Serve the size you render.** A 4000px original in a 320px thumbnail is the
most common waste in an app that has pictures at all. If the chosen storage
resizes on request, ask it for the size the page needs and build that URL at
render time; if it does not, write a thumbnail at upload time. Either way the
database holds what identifies the object, not a URL with a size baked into
it.

## Verifying it

An E2E journey uploads a small real file through the interface, waits for the
picture to appear, reloads the page and finds it still there — because an
upload that only exists in component state is not an upload.

Unit tests own the boundaries: an oversized file is rejected, a file that is
not an image is rejected whatever it is called, an anonymous request is
refused, one user cannot delete another's picture, and deleting a record
removes the object it named.

Use a small fixture image committed to the repository — a few hundred bytes is
enough. Never upload a real customer's photo in a test.

The provider's own file carries its references.
