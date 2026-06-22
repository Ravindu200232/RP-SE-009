"""Next.js API route generator (App Router) for the planned data model.

Per entity it generates:
* `src/app/api/<collection>/route.js`     — GET list (search + ref filters +
  pagination + populated refs) and POST create (via the service layer).
* `src/app/api/<collection>/[id]/route.js`— GET by id (populated), PATCH update,
  DELETE (relation-guarded), all via the service layer.

Routes never embed workflow logic — they delegate create/update/delete to the
generated services so relationship side effects run consistently.

Mutating verbs (POST/PATCH/DELETE) are guarded by `canAccess(role, collection)`
from `@/lib/access` — `role` comes from the `x-user-role` header the client
(`lib/api.js`) attaches from the localStorage session. GET stays open: read
access wasn't asked for and `canAccess`'s no-entry-means-open default already
covers collections nobody restricted.
"""
from __future__ import annotations


API_AUTH_HELPER = """// AUTO-GENERATED: reads the caller's role from the request, set by the
// client (lib/api.js) from the localStorage session. This is the same
// prototype-grade trust model the rest of this app's mock auth already uses -
// not a cryptographic session, just enough to enforce the planned role rules.
export function roleFromRequest(req) {
  return req.headers.get('x-user-role') || null;
}
"""


def generate_collection_route(entity) -> str:
    name = entity["name"]
    coll = entity["collection"]
    return f"""// AUTO-GENERATED API: list + create for {name}.
import {{ NextResponse }} from 'next/server';
import {{ {name} }} from '@/lib/models/{name}';
import {{ listDocs, populateMany }} from '@/lib/orm';
import {{ create{name} }} from '@/lib/services/{name}Service';
import {{ canAccess }} from '@/lib/access';
import {{ roleFromRequest }} from '@/lib/apiAuth';

export const dynamic = 'force-dynamic';

export async function GET(req) {{
  const {{ searchParams }} = new URL(req.url);
  const search = searchParams.get('q') || '';
  const page = Number(searchParams.get('page') || 1);
  const filter = {{}};
  for (const ref of {name}.refs) {{
    const v = searchParams.get(ref.field);
    if (v) filter[ref.field] = v;
  }}
  const res = await listDocs({name}.collection, {{ search, filter, page, limit: 50 }});
  res.rows = await populateMany(res.rows, {name}.refs);
  return NextResponse.json(res);
}}

export async function POST(req) {{
  if (!canAccess(roleFromRequest(req), '{coll}')) {{
    return NextResponse.json({{ error: 'Forbidden' }}, {{ status: 403 }});
  }}
  let body = {{}};
  try {{ body = await req.json(); }} catch (e) {{ return NextResponse.json({{ error: 'Invalid JSON body' }}, {{ status: 400 }}); }}
  try {{
    const rec = await create{name}(body && typeof body === 'object' ? body : {{}});
    return NextResponse.json(rec, {{ status: 201 }});
  }} catch (err) {{
    return NextResponse.json({{ error: err.message || 'Create failed' }}, {{ status: err.status || 400 }});
  }}
}}
"""


def generate_item_route(entity) -> str:
    name = entity["name"]
    coll = entity["collection"]
    return f"""// AUTO-GENERATED API: read + update + delete for {name}.
import {{ NextResponse }} from 'next/server';
import {{ {name} }} from '@/lib/models/{name}';
import {{ getDoc, populateDoc }} from '@/lib/orm';
import {{ update{name}, delete{name} }} from '@/lib/services/{name}Service';
import {{ canAccess }} from '@/lib/access';
import {{ roleFromRequest }} from '@/lib/apiAuth';

export const dynamic = 'force-dynamic';

export async function GET(_req, {{ params }}) {{
  const doc = await getDoc({name}.collection, params.id);
  if (!doc) return NextResponse.json({{ error: 'Not found' }}, {{ status: 404 }});
  return NextResponse.json(await populateDoc(doc, {name}.refs));
}}

export async function PATCH(req, {{ params }}) {{
  if (!canAccess(roleFromRequest(req), '{coll}')) {{
    return NextResponse.json({{ error: 'Forbidden' }}, {{ status: 403 }});
  }}
  let body = {{}};
  try {{ body = await req.json(); }} catch (e) {{ return NextResponse.json({{ error: 'Invalid JSON body' }}, {{ status: 400 }}); }}
  try {{
    const rec = await update{name}(params.id, body && typeof body === 'object' ? body : {{}});
    if (!rec) return NextResponse.json({{ error: 'Not found' }}, {{ status: 404 }});
    return NextResponse.json(rec);
  }} catch (err) {{
    return NextResponse.json({{ error: err.message || 'Update failed' }}, {{ status: err.status || 400 }});
  }}
}}

export async function DELETE(req, {{ params }}) {{
  if (!canAccess(roleFromRequest(req), '{coll}')) {{
    return NextResponse.json({{ error: 'Forbidden' }}, {{ status: 403 }});
  }}
  try {{
    const ok = await delete{name}(params.id);
    return NextResponse.json({{ ok }});
  }} catch (err) {{
    return NextResponse.json({{ error: err.message || 'Delete failed' }}, {{ status: err.status || 409 }});
  }}
}}
"""
