"""Deterministic component-wise frontend compiler for role-wise SRS apps."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _pascal(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(value or "Section"))
    return "".join(x[:1].upper() + x[1:] for x in parts) or "Section"


def _safe_segment(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "shared").lower()).strip("-") or "shared"


def _route_dir(path: str) -> str:
    clean = str(path or "/").strip("/")
    return f"app/{clean}" if clean else "app"


def _feature_path(contract: dict) -> str:
    feature = _safe_segment((contract.get("allowed_resources") or ["shared"])[0])
    return f"components/features/{feature}/{contract['name']}.tsx"


def _import_path(path: str) -> str:
    return "@/" + path.rsplit(".", 1)[0]


def _field_meta(spec: dict, resource_name: str, allowed: list[str]) -> list[dict]:
    resource = next((r for r in (spec.get("resources") or []) if r.get("name") == resource_name), None)
    fields = (resource or {}).get("fields") or []
    allowed_set = set(allowed or [])
    values = [f for f in fields if not allowed_set or f.get("name") in allowed_set]
    return [f for f in values if f.get("name") not in {"passwordHash", "password"}][:8]


def _display_component(contract: dict) -> str:
    name = contract["name"]
    kind = contract.get("type") or "display"
    return f'''\'use client\'

import {{ useEffect, useMemo, useState }} from 'react'
import {{ Alert, AlertDescription, AlertTitle }} from '@/components/ui/alert'
import {{ Badge }} from '@/components/ui/badge'
import {{ Card, CardContent, CardDescription, CardHeader, CardTitle }} from '@/components/ui/card'
import {{ Skeleton }} from '@/components/ui/skeleton'
import {{ Table, TableBody, TableCell, TableHead, TableHeader, TableRow }} from '@/components/ui/table'

export interface {name}Props {{
  title?: string
  resource?: string
  fields?: string[]
  content?: string[]
  actions?: string[]
}}

export default function {name}({{
  title = {json.dumps(name)}, resource = '', fields = [], content = [], actions = [],
}}: {name}Props) {{
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(Boolean(resource))
  const [error, setError] = useState('')
  useEffect(() => {{
    if (!resource) return
    let active = true
    fetch(resource)
      .then(async (response) => {{
        const payload = await response.json()
        if (!response.ok) throw new Error(payload?.error || `Request failed (${{response.status}})`)
        return payload?.data ?? payload
      }})
      .then((value) => {{ if (active) setRows(Array.isArray(value) ? value : value ? [value] : []) }})
      .catch((reason) => {{ if (active) setError(reason?.message || 'Unable to load data') }})
      .finally(() => {{ if (active) setLoading(false) }})
    return () => {{ active = false }}
  }}, [resource])
  const columns = useMemo(() => fields.length ? fields : Object.keys(rows[0] || {{}}).filter((x) => !['__v','passwordHash'].includes(x)).slice(0, 6), [fields, rows])
  if (loading) return <Card><CardHeader><Skeleton className="h-6 w-44" /></CardHeader><CardContent><Skeleton className="h-28 w-full" /></CardContent></Card>
  if (error) return <Alert className="border-rose-500/30"><AlertTitle>{{title}}</AlertTitle><AlertDescription>{{error}}</AlertDescription></Alert>
  return (
    <Card data-component={json.dumps(name)} data-component-kind={json.dumps(kind)}>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div><CardTitle>{{title}}</CardTitle><CardDescription>{{content[0] || `${{rows.length}} current record${{rows.length === 1 ? '' : 's'}}`}}</CardDescription></div>
        <div className="flex flex-wrap justify-end gap-2">{{actions.slice(0,3).map((action) => <Badge key={{action}}>{{action}}</Badge>)}}</div>
      </CardHeader>
      <CardContent>
        {{rows.length > 0 ? (
          <Table><TableHeader><TableRow>{{columns.map((column) => <TableHead key={{column}}>{{column.replace(/([A-Z])/g, ' $1')}}</TableHead>)}}</TableRow></TableHeader>
          <TableBody>{{rows.slice(0,8).map((row, index) => <TableRow key={{String(row._id || index)}}>{{columns.map((column) => <TableCell key={{column}}>{{String(row[column] ?? '—')}}</TableCell>)}}</TableRow>)}}</TableBody></Table>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-400">{{content[1] || 'No records yet. This view will update when data is added.'}}</div>
        )}}
      </CardContent>
    </Card>
  )
}}
'''


def _navigation_component(contract: dict) -> str:
    name = contract["name"]
    return f'''import Sidebar, {{ type SidebarLink }} from '@/components/Sidebar'

export interface {name}Props {{ role: string; label: string; links: SidebarLink[] }}
export default function {name}({{ role, label, links }}: {name}Props) {{
  return <Sidebar role={{role}} label={{label}} links={{links}} />
}}
'''


def _layout_component(contract: dict) -> str:
    name = contract["name"]
    return f'''import {{ type ReactNode }} from 'react'

export interface {name}Props {{ children: ReactNode; sidebar?: ReactNode }}
export default function {name}({{ children, sidebar }}: {name}Props) {{
  return <div className="flex min-h-[calc(100vh-4rem)] bg-slate-950">{{sidebar}}<main className="min-w-0 flex-1 p-4 sm:p-5 md:p-8">{{children}}</main></div>
}}
'''


def _form_field(field: dict) -> str:
    name = str(field.get("name") or "field")
    label = re.sub(r"([A-Z])", r" \1", name).strip().title()
    if field.get("enum"):
        options = "".join(f"<option value={json.dumps(str(v))}>{str(v).replace('_', ' ').title()}</option>" for v in field["enum"])
        return f'''<div className="space-y-2"><Label htmlFor="{name}">{label}</Label><Select id="{name}" value={{form.{name} || ''}} onChange={{(event) => update('{name}', event.target.value)}} required={{{str(bool(field.get('required'))).lower()}}}><option value="">Select {label}</option>{options}</Select></div>'''
    input_type = "number" if field.get("type") == "Number" else "date" if field.get("type") == "Date" else "text"
    return f'''<div className="space-y-2"><Label htmlFor="{name}">{label}</Label><Input id="{name}" type="{input_type}" value={{form.{name} || ''}} onChange={{(event) => update('{name}', event.target.value)}} required={{{str(bool(field.get('required'))).lower()}}} /></div>'''


def _form_component(contract: dict, spec: dict) -> str:
    name = contract["name"]
    resource_name = (contract.get("allowed_resources") or [""])[0]
    fields = _field_meta(spec, resource_name, contract.get("allowed_fields") or [])
    field_names = [f["name"] for f in fields]
    field_jsx = "\n          ".join(_form_field(f) for f in fields)
    initial = ", ".join(f"{f}: ''" for f in field_names)
    conversions = []
    for field in fields:
        if field.get("type") == "Number":
            conversions.append(f"{field['name']}: Number(form.{field['name']})")
    payload = f"{{ ...form, {', '.join(conversions)} }}" if conversions else "form"
    has_fields = bool(fields)
    has_text_fields = any(not field.get("enum") for field in fields)
    has_enum_fields = any(field.get("enum") for field in fields)
    control_imports = []
    if has_text_fields:
        control_imports.append("import { Input } from '@/components/ui/input'")
    if has_fields:
        control_imports.append("import { Label } from '@/components/ui/label'")
    if has_enum_fields:
        control_imports.append("import { Select } from '@/components/ui/select'")
    update_helper = (
        "  const update = (field: string, value: string) => setForm((current) => ({ ...current, [field]: value }))\n"
        if has_fields else ""
    )
    return f'''\'use client\'

import {{ FormEvent, useState }} from 'react'
import {{ Alert, AlertDescription }} from '@/components/ui/alert'
import {{ Button }} from '@/components/ui/button'
import {{ Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle }} from '@/components/ui/card'
{chr(10).join(control_imports)}

export interface {name}Props {{ title?: string; resource?: string; fields?: string[]; content?: string[]; actions?: string[] }}
export default function {name}({{ title = {json.dumps(name)}, resource = '', actions = [] }}: {name}Props) {{
  const [form, setForm] = useState<Record<string,string>>({{ {initial} }})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
{update_helper.rstrip()}
  async function submit(event: FormEvent) {{
    event.preventDefault(); setError(''); setMessage('')
    if (!resource) {{ setError('This form has no declared data resource.'); return }}
    setSaving(true)
    try {{
      const response = await fetch(resource, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({payload}) }})
      const payload = await response.json()
      if (!response.ok) throw new Error(payload?.error || `Save failed (${{response.status}})`)
      setMessage('Saved successfully')
      setForm({{ {initial} }})
    }} catch (reason: any) {{ setError(reason?.message || 'Unable to save') }} finally {{ setSaving(false) }}
  }}
  return <Card data-component={json.dumps(name)} data-component-kind="form"><form onSubmit={{submit}}><CardHeader><CardTitle>{{title}}</CardTitle><CardDescription>{{actions[0] || 'Complete the required information.'}}</CardDescription></CardHeader><CardContent className="grid gap-4 md:grid-cols-2">{field_jsx or '<p className="text-sm text-slate-400">No editable fields were declared.</p>'}{{error && <Alert className="md:col-span-2 border-rose-500/30"><AlertDescription>{{error}}</AlertDescription></Alert>}}{{message && <Alert className="md:col-span-2 border-emerald-500/30"><AlertDescription>{{message}}</AlertDescription></Alert>}}</CardContent><CardFooter><Button type="submit" disabled={{saving || !resource}}>{{saving ? 'Saving…' : (actions[0] || 'Save')}}</Button></CardFooter></form></Card>
}}
'''


def component_source(contract: dict, spec: dict) -> str:
    kind = str(contract.get("type") or "display").lower()
    if kind == "navigation":
        return _navigation_component(contract)
    if kind == "layout":
        return _layout_component(contract)
    if kind in {"form", "form_control", "transaction_form"}:
        return _form_component(contract, spec)
    return _display_component(contract)


def _section_source(page: dict, section: dict, contract_by_name: dict[str, dict]) -> tuple[str, str]:
    section_component = _pascal(section["section_name"]) + "Section"
    imports = []
    blocks = []
    resource_name = (page.get("resources") or [""])[0]
    from agents.scaffold import route_name
    resource_api = f"/api/{route_name(resource_name)}" if resource_name else ""
    for component_name in section.get("components") or []:
        contract = contract_by_name[component_name]
        imports.append(f"import {component_name} from '{_import_path(_feature_path(contract))}'")
        fields = contract.get("allowed_fields") or []
        actions = page.get("functions") or []
        blocks.append(
            f"      <{component_name} title={{{json.dumps(component_name)}}} "
            f"resource={{{json.dumps(resource_api)}}} fields={{{json.dumps(fields)}}} "
            f"content={{{json.dumps(section.get('content') or [])}}} actions={{{json.dumps(actions)}}} />"
        )
    source = "\n".join(imports) + f'''\n\nexport default function {section_component}() {{
  return (
    <section data-section={json.dumps(section['section_name'])} className="space-y-5">
      <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-300">Workspace</p><h2 className="mt-2 text-2xl font-bold text-white">{section['section_name']}</h2></div>
{chr(10).join(blocks) if blocks else '      <p className="text-slate-400">No components were declared for this section.</p>'}
    </section>
  )
}}
'''
    return section_component, source


def _page_source(page: dict, sections: list[tuple[str, str]]) -> str:
    imports = ["import { redirect } from 'next/navigation'", "import { getSession } from '@/lib/auth'"]
    for component, rel in sections:
        imports.append(f"import {component} from './_components/{Path(rel).stem}'")
    role = page.get("owner_role") or ""
    return "\n".join(imports) + f'''\n\nexport const dynamic = 'force-dynamic'

export default async function Page() {{
  const session = await getSession()
  if (!session) redirect('/login')
  if (session.role !== {json.dumps(role)}) redirect('/login')
  const pageContext = {{ role: session.role, userId: session.userId, route: {json.dumps(page['path'])} }}
  return (
    <div className="mx-auto max-w-[1600px] space-y-8" data-page={json.dumps(page['path'])} data-role={{pageContext.role}}>
      <header className="overflow-hidden rounded-3xl border border-indigo-400/15 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 p-7 shadow-2xl shadow-black/20">
        <p className="text-sm font-semibold text-indigo-300">{str(page.get('owner_role') or '').replace('_',' ').title()} workspace</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-white md:text-4xl">{page.get('title') or 'Workspace'}</h1>
        <p className="mt-3 max-w-3xl text-slate-400">Manage this workflow with live, persisted application data.</p>
      </header>
{chr(10).join(f'      <{component} />' for component, _ in sections)}
    </div>
  )
}}
'''


def _role_layout_files(spec: dict, contract_by_name: dict[str, dict]) -> dict[str, str]:
    files = {}
    for role in spec.get("roles") or []:
        role_name = role["name"]
        pages = [p for p in (spec.get("pages") or []) if p.get("owner_role") == role_name]
        if not pages:
            continue
        top = str(pages[0]["path"]).strip("/").split("/", 1)[0]
        declared = [c for c in contract_by_name.values() if c.get("declared") and role_name in (c.get("roles") or [])]
        nav = next((c for c in declared if c.get("type") == "navigation"), None)
        layout = next((c for c in declared if c.get("type") == "layout"), None)
        imports = ["import { redirect } from 'next/navigation'", "import { getSession } from '@/lib/auth'"]
        if nav:
            imports.append(f"import {nav['name']} from '{_import_path(_feature_path(nav))}'")
        else:
            imports.append("import Sidebar, { type SidebarLink } from '@/components/Sidebar'")
        if layout:
            imports.append(f"import {layout['name']} from '{_import_path(_feature_path(layout))}'")
        links = [{"href": p["path"], "label": p.get("title") or p["path"]} for p in pages]
        nav_expr = (
            f"<{nav['name']} role={{{json.dumps(role_name)}}} label={{{json.dumps(role['label'])}}} links={{LINKS}} />"
            if nav else
            f"<Sidebar role={{{json.dumps(role_name)}}} label={{{json.dumps(role['label'])}}} links={{LINKS}} />"
        )
        if layout:
            body = f"<{layout['name']} sidebar={{{nav_expr}}}>{{children}}</{layout['name']}>"
        else:
            body = f"<div className=\"flex min-h-[calc(100vh-4rem)] bg-slate-950\">{nav_expr}<main className=\"min-w-0 flex-1 p-4 sm:p-5 md:p-8\">{{children}}</main></div>"
        source = "\n".join(imports) + f'''\n\nconst LINKS = {json.dumps(links)}

export default async function RoleLayout({{ children }}: {{ children: React.ReactNode }}) {{
  const session = await getSession()
  if (!session) redirect('/login')
  if (session.role !== {json.dumps(role_name)}) redirect('/login')
  return ({body})
}}
'''
        files[f"app/{top}/layout.tsx"] = source
    return files


def compile_component_pages(spec: dict) -> dict[str, str]:
    files: dict[str, str] = {}
    contract_by_name = {c["name"]: c for c in spec.get("component_contracts") or []}
    for contract in contract_by_name.values():
        files[_feature_path(contract)] = component_source(contract, spec)
    files.update(_role_layout_files(spec, contract_by_name))
    for page in spec.get("pages") or []:
        if page.get("kind") == "auth":
            continue
        route_dir = _route_dir(page["path"])
        section_files = []
        used_names = set()
        for index, section in enumerate(page.get("sections") or []):
            component_name, source = _section_source(page, section, contract_by_name)
            if component_name in used_names:
                component_name += str(index + 1)
            used_names.add(component_name)
            rel = f"{route_dir}/_components/{component_name}.tsx"
            files[rel] = source.replace(
                f"export default function {_pascal(section['section_name'])}Section()",
                f"export default function {component_name}()",
            )
            section_files.append((component_name, rel))
        files[f"{route_dir}/page.tsx"] = _page_source(page, section_files)
    files["app/page.tsx"] = "import { redirect } from 'next/navigation'\nexport default function Home(){ redirect('/login') }\n"
    return files
