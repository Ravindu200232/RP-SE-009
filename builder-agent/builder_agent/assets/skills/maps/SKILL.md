---
name: maps
description: Showing a map, finding a place and turning an address into coordinates — which credentials to ask for, why the key is restricted rather than hidden, and how to keep a map from costing money on every keystroke.
---

# Maps and places

Use this skill when the product shows somewhere on a map, asks a person to
pick a location, or turns a typed address into coordinates to store.

## What was already settled

A maps key cannot be read out of a repository, so it was asked for before the
build started, or ticked as a plugin. That answer is in the plan under "already
settled". Build the one provider that was chosen and read its file and no
other; do not write a switch between them.

- **Google Maps** — `readSkill("maps", "google-maps.md")`
- **Mapbox** — `readSkill("maps", "mapbox.md")`

The settings are in `.env.local` under the names the question used. Whichever
provider's names are present in the environment is the one that was chosen.

## What has to be true

**A browser key is public, so restrict it rather than hide it.** A map draws in
the browser, which means the key is in the page and anyone can read it. That is
not the leak — the leak is an unrestricted key. Say in your report that the key
must be restricted to the product's own domains (and its Android/iOS bundle ids
if there are apps) in the provider's console, because that is the only thing
standing between a public key and somebody else's bill.

**A key that geocodes is a different key.** Turning an address into coordinates
happens on the server, against a key that is never sent to the browser, and it
is restricted by IP rather than by domain. Do not reuse the map key for it and
do not put the server key anywhere a page can reach.

**Do not geocode on every keystroke.** An autocomplete field that calls the
provider per character is a bill, not a feature. Use the provider's own session
tokens where it has them, debounce, and cache what you resolve — an address
resolves to the same point tomorrow.

**Store the coordinates, not only the text.** An address typed by a person is
not a location: it is a string that moves, abbreviates and misspells. Store the
latitude and longitude you resolved alongside the text, and treat the text as
what to show rather than what to search on.

**The map is not the only way to read the page.** A place shown only as a pin
is invisible to anyone not looking at pixels. Put the address in text beside
the map, give the container an accessible name, and make whatever the map does
reachable without it.

**A missing key fails loudly.** Render nothing and say why, naming the missing
variable. A map container that silently stays grey is a bug report nobody can
write.

## Verifying it

Unit tests own the geocoding boundary with the provider stubbed: an address
that resolves is stored with its coordinates, one that does not is recorded as
unresolved rather than as `0,0`, and a provider error does not lose the record
the user was saving.

An E2E journey cannot assert on a third-party map canvas and must not try.
Assert what the product owns: the address text is on the page, the container
rendered with its accessible name, and the coordinates reached the record.
