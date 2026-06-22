"""SRS-driven page generator.

Turns each entry in srs["app_pages"] into a real Next.js page file at the
exact route the SRS specifies. Specialized page types get full custom UI;
admin-CRUD pages get lightweight wrappers that link to /manage/{collection}.

Page types produced:
  /pos*               → POS workflow page (barcode scan, cart, payment panel, receipt)
  *report*            → Report dashboard (one tab per reporting_requirement)
  /customer/*         → Customer portal page
  /admin/dashboard    → redirect to /dashboard
  /admin/*            → admin section page with function cards + link to manage
  anything else       → generic stub showing page title + function list
"""
from __future__ import annotations

import os
import re


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_route(route: str) -> str:
    """Strip leading slash; keep inner slashes → nested dir path."""
    return re.sub(r"[^a-zA-Z0-9/_-]", "", route).strip("/")


def _page_path(route: str) -> str:
    """SRS route → Next.js App-Router file path inside src/app/(app)/."""
    safe = _safe_route(route)
    return f"src/app/(app)/{safe}/page.jsx"


def _slug_from_route(route: str) -> str:
    """'/admin/purchase-orders' → 'purchaseorders'."""
    return re.sub(r"[^a-z0-9]", "", route.lower())


def _clean_nav_label(s: str) -> str:
    """Sidebar labels read as the noun, not 'X Management' (user wants 'Brand')."""
    s = str(s or "").strip()
    cleaned = re.sub(r"\s+(Management System|Management|System|Module|Center|Centre)$", "", s, flags=re.I).strip()
    return cleaned or s


def _label(s: str) -> str:
    return re.sub(r"[-_/]+", " ", s).strip().title()


def _js_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")


def _roles_js(roles: list) -> str:
    return "[" + ", ".join(f"'{_js_str(r)}'" for r in roles) + "]"


# ── POS page ─────────────────────────────────────────────────────────────────

_POS_PAGE = """\
'use client';
// AUTO-GENERATED: POS workflow page — {page_name}
// SRS roles: {roles_comment}
// SRS functions: {funcs_comment}
import * as React from 'react';

const TAX_RATE = 0.05;

export default function PosPage() {{
  const [barcode, setBarcode] = React.useState('');
  const [search, setSearch] = React.useState('');
  const [cart, setCart] = React.useState([]);
  const [customer, setCustomer] = React.useState('');
  const [payMethod, setPayMethod] = React.useState('cash');
  const [cashGiven, setCashGiven] = React.useState('');
  const [discount, setDiscount] = React.useState(0);
  const [receiptVisible, setReceiptVisible] = React.useState(false);
  const [products, setProducts] = React.useState([]);

  React.useEffect(() => {{
    if (search.length > 1) {{
      fetch('/api/{catalog_collection}?q=' + encodeURIComponent(search))
        .then((r) => r.json())
        .then((d) => setProducts(Array.isArray(d.rows) ? d.rows : []))
        .catch(() => {{}});
    }} else {{
      setProducts([]);
    }}
  }}, [search]);

  function addToCart(product) {{
    setCart((prev) => {{
      const idx = prev.findIndex((i) => i.id === product.id);
      if (idx >= 0) {{
        const next = [...prev];
        next[idx] = {{ ...next[idx], qty: next[idx].qty + 1 }};
        return next;
      }}
      return [...prev, {{ ...product, qty: 1, unitPrice: product.unit_price || product.unitPrice || 0 }}];
    }});
    setSearch('');
    setProducts([]);
  }}

  function updateQty(id, qty) {{
    if (qty <= 0) {{ setCart((p) => p.filter((i) => i.id !== id)); return; }}
    setCart((p) => p.map((i) => i.id === id ? {{ ...i, qty }} : i));
  }}

  function handleBarcodeSubmit(e) {{
    e.preventDefault();
    if (!barcode) return;
    fetch('/api/{catalog_collection}?q=' + encodeURIComponent(barcode))
      .then((r) => r.json())
      .then((d) => {{
        const rows = Array.isArray(d.rows) ? d.rows : [];
        if (rows[0]) addToCart(rows[0]);
      }})
      .catch(() => {{}});
    setBarcode('');
  }}

  const subtotal = cart.reduce((s, i) => s + i.unitPrice * i.qty, 0);
  const discountAmt = subtotal * (discount / 100);
  const tax = (subtotal - discountAmt) * TAX_RATE;
  const total = subtotal - discountAmt + tax;
  const change = Number(cashGiven) - total;

  function processSale() {{
    const body = {{
      items: cart.map((i) => ({{ productId: i.id, qty: i.qty, unitPrice: i.unitPrice }})),
      customerId: customer || undefined,
      paymentMethod: payMethod,
      discount: discountAmt,
      tax,
      total,
    }};
    fetch('/api/{sale_collection}', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }})
      .then((r) => r.json())
      .then(() => {{ setReceiptVisible(true); }})
      .catch(() => {{}});
  }}

  function newSale() {{
    setCart([]); setDiscount(0); setCashGiven(''); setCustomer('');
    setPayMethod('cash'); setReceiptVisible(false);
  }}

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{page_name_jsx}</h1>
        <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">{page_type_badge}</span>
      </div>

      {{receiptVisible ? (
        <div className="mx-auto max-w-sm rounded-xl border bg-white p-6 text-center shadow">
          <h2 className="text-xl font-bold mb-2">Sale Complete</h2>
          <p className="text-muted-foreground text-sm mb-4">Receipt</p>
          <table className="w-full text-sm mb-4">
            <tbody>
              {{cart.map((i) => (
                <tr key={{i.id}}>
                  <td className="text-left py-0.5">{{i.name || i.{catalog_name_field}}}</td>
                  <td className="text-right">{{i.qty}} × {{Number(i.unitPrice).toFixed(2)}}</td>
                </tr>
              ))}}
              <tr className="border-t font-semibold"><td>Total</td><td className="text-right">{{total.toFixed(2)}}</td></tr>
              {{payMethod === 'cash' && <tr><td>Change</td><td className="text-right">{{Math.max(0, change).toFixed(2)}}</td></tr>}}
            </tbody>
          </table>
          <button onClick={{newSale}} className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white">New Sale</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {{/* Left panel */}}
          <div className="lg:col-span-2 space-y-4">
            {{/* Barcode scan */}}
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <form onSubmit={{handleBarcodeSubmit}} className="flex gap-2">
                <input
                  className="flex-1 rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                  placeholder="Scan barcode or enter {catalog_label_lower} code..."
                  value={{barcode}}
                  onChange={{(e) => setBarcode(e.target.value)}}
                  autoFocus
                />
                <button type="submit" className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white">Scan</button>
              </form>
            </div>

            {{/* Product search */}}
            <div className="rounded-xl border bg-white p-4 shadow-sm relative">
              <input
                className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                placeholder="Search {catalog_label_lower} by name..."
                value={{search}}
                onChange={{(e) => setSearch(e.target.value)}}
              />
              {{products.length > 0 && (
                <ul className="absolute left-4 right-4 top-16 z-10 rounded-lg border bg-white shadow-lg max-h-48 overflow-y-auto">
                  {{products.map((p) => (
                    <li key={{p.id}} className="cursor-pointer px-4 py-2 text-sm hover:bg-primary/10" onClick={{() => addToCart(p)}}>
                      {{p.name || p.{catalog_name_field}}} — <span className="text-muted-foreground">{{p.unit_price || p.unitPrice || 0}}</span>
                    </li>
                  ))}}
                </ul>
              )}}
            </div>

            {{/* Cart */}}
            <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 text-left">{catalog_label}</th>
                    <th className="px-4 py-3 text-right">Price</th>
                    <th className="px-4 py-3 text-center">Qty</th>
                    <th className="px-4 py-3 text-right">Subtotal</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {{cart.length === 0 ? (
                    <tr><td colSpan={{5}} className="py-8 text-center text-sm text-muted-foreground">Cart is empty — scan or search a {catalog_label_lower}</td></tr>
                  ) : cart.map((item) => (
                    <tr key={{item.id}}>
                      <td className="px-4 py-2">{{item.name || item.{catalog_name_field}}}</td>
                      <td className="px-4 py-2 text-right">{{Number(item.unitPrice).toFixed(2)}}</td>
                      <td className="px-4 py-2">
                        <div className="flex items-center justify-center gap-2">
                          <button onClick={{() => updateQty(item.id, item.qty - 1)}} className="rounded border px-2 text-sm">-</button>
                          <span>{{item.qty}}</span>
                          <button onClick={{() => updateQty(item.id, item.qty + 1)}} className="rounded border px-2 text-sm">+</button>
                        </div>
                      </td>
                      <td className="px-4 py-2 text-right">{{(item.unitPrice * item.qty).toFixed(2)}}</td>
                      <td className="px-4 py-2 text-center">
                        <button onClick={{() => updateQty(item.id, 0)}} className="text-red-500 text-xs">✕</button>
                      </td>
                    </tr>
                  ))}}
                </tbody>
              </table>
            </div>
          </div>

          {{/* Right panel — payment */}}
          <div className="space-y-4">
            {{/* Customer */}}
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <label className="block text-xs font-medium text-muted-foreground mb-1">Customer (optional)</label>
              <input
                className="w-full rounded-lg border px-3 py-2 text-sm"
                placeholder="Customer name or phone..."
                value={{customer}}
                onChange={{(e) => setCustomer(e.target.value)}}
              />
            </div>

            {{/* Discount */}}
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <label className="block text-xs font-medium text-muted-foreground mb-1">Discount %</label>
              <input
                type="number" min="0" max="100"
                className="w-full rounded-lg border px-3 py-2 text-sm"
                value={{discount}}
                onChange={{(e) => setDiscount(Number(e.target.value))}}
              />
            </div>

            {{/* Totals */}}
            <div className="rounded-xl border bg-white p-4 shadow-sm space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Subtotal</span><span>{{subtotal.toFixed(2)}}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Discount</span><span>-{{discountAmt.toFixed(2)}}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Tax (5%)</span><span>{{tax.toFixed(2)}}</span></div>
              <div className="flex justify-between font-bold text-base border-t pt-2"><span>Total</span><span>{{total.toFixed(2)}}</span></div>
            </div>

            {{/* Payment method */}}
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <label className="block text-xs font-medium text-muted-foreground mb-2">Payment Method</label>
              <div className="flex gap-2">
                {{['cash', 'card', 'transfer'].map((m) => (
                  <button key={{m}} onClick={{() => setPayMethod(m)}}
                    className={{`flex-1 rounded-lg border py-2 text-sm font-medium capitalize ${{payMethod === m ? 'bg-primary text-white border-primary' : 'hover:border-primary/50'}}`}}>
                    {{m}}
                  </button>
                ))}}
              </div>
            </div>

            {{payMethod === 'cash' && (
              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <label className="block text-xs font-medium text-muted-foreground mb-1">Cash Given</label>
                <input
                  type="number"
                  className="w-full rounded-lg border px-3 py-2 text-sm"
                  value={{cashGiven}}
                  onChange={{(e) => setCashGiven(e.target.value)}}
                />
                {{cashGiven && <p className="mt-1 text-xs text-muted-foreground">Change: {{Math.max(0, change).toFixed(2)}}</p>}}
              </div>
            )}}

            <button
              disabled={{cart.length === 0}}
              onClick={{processSale}}
              className="w-full rounded-xl bg-primary py-3 text-sm font-bold text-white disabled:opacity-40 hover:bg-primary/90 transition"
            >
              Process Sale — {{total.toFixed(2)}}
            </button>
          </div>
        </div>
      )}}
    </div>
  );
}}
"""


# ── Reports page ──────────────────────────────────────────────────────────────

_REPORTS_PAGE = """\
'use client';
// AUTO-GENERATED: Reports dashboard — {page_name}
// SRS roles: {roles_comment}
import * as React from 'react';

const REPORTS = {reports_json};

export default function ReportsPage() {{
  const [activeReport, setActiveReport] = React.useState(REPORTS[0]?.name || '');
  const [from, setFrom] = React.useState('');
  const [to, setTo] = React.useState('');
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  function loadReport() {{
    const rep = REPORTS.find((r) => r.name === activeReport);
    if (!rep) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    params.set('report', rep.name);
    fetch('/api/reports?' + params.toString())
      .then((r) => r.json())
      .then((d) => {{ setRows(Array.isArray(d.rows) ? d.rows : Array.isArray(d) ? d : []); }})
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }}

  function exportCSV() {{
    if (!rows.length) return;
    const headers = Object.keys(rows[0]);
    const csv = [headers.join(','), ...rows.map((r) => headers.map((h) => JSON.stringify(r[h] ?? '')).join(','))].join('\\n');
    const blob = new Blob([csv], {{ type: 'text/csv' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = activeReport + '.csv'; a.click();
  }}

  const rep = REPORTS.find((r) => r.name === activeReport);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{page_name_jsx}</h1>
        <button onClick={{exportCSV}} disabled={{!rows.length}}
          className="rounded-lg border px-4 py-2 text-sm font-medium hover:border-primary/50 disabled:opacity-40">
          Export CSV
        </button>
      </div>

      {{/* Report tabs */}}
      <div className="flex flex-wrap gap-2">
        {{REPORTS.map((r) => (
          <button key={{r.name}} onClick={{() => {{ setActiveReport(r.name); setRows([]); }}}}
            className={{`rounded-full px-4 py-1.5 text-sm font-medium border ${{activeReport === r.name ? 'bg-primary text-white border-primary' : 'hover:border-primary/50'}}`}}>
            {{r.name}}
          </button>
        ))}}
      </div>

      {{/* Filters */}}
      <div className="rounded-xl border bg-card p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">From</label>
            <input type="date" value={{from}} onChange={{(e) => setFrom(e.target.value)}}
              className="rounded-lg border px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">To</label>
            <input type="date" value={{to}} onChange={{(e) => setTo(e.target.value)}}
              className="rounded-lg border px-3 py-2 text-sm" />
          </div>
          {{rep?.filters?.map((f) => (
            <div key={{f}}>
              <label className="block text-xs text-muted-foreground mb-1 capitalize">{{f}}</label>
              <input className="rounded-lg border px-3 py-2 text-sm" placeholder={{f}} />
            </div>
          ))}}
          <button onClick={{loadReport}} className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-white">
            {{loading ? 'Loading…' : 'Run Report'}}
          </button>
        </div>
      </div>

      {{/* Results */}}
      {{rows.length > 0 ? (
        <div className="rounded-xl border bg-card overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-muted-foreground">
              <tr>{{Object.keys(rows[0]).map((h) => <th key={{h}} className="px-4 py-3 text-left capitalize">{{h.replace(/_/g,' ')}}</th>)}}</tr>
            </thead>
            <tbody className="divide-y">
              {{rows.map((row, i) => (
                <tr key={{i}}>{{Object.values(row).map((v, j) => <td key={{j}} className="px-4 py-2">{{String(v ?? '')}}</td>)}}</tr>
              ))}}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border bg-card p-12 text-center text-sm text-muted-foreground">
          Select a report and click Run Report to view results.
        </div>
      )}}
    </div>
  );
}}
"""


# ── Customer portal dashboard ─────────────────────────────────────────────────

_CUSTOMER_DASH = """\
'use client';
// AUTO-GENERATED: Customer portal — {page_name}
import * as React from 'react';
import Link from 'next/link';

const SECTIONS = {sections_json};

export default function CustomerDashboardPage() {{
  const [orders, setOrders] = React.useState([]);

  React.useEffect(() => {{
    fetch('/api/{txn_collection}?customer=me')
      .then((r) => r.json()).then((d) => setOrders(Array.isArray(d.rows) ? d.rows : [])).catch(() => {{}});
  }}, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{page_name_jsx}</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {{SECTIONS.map((s) => (
          <div key={{s.label}} className="rounded-xl border bg-card p-5 hover:shadow-md transition">
            <p className="text-sm text-muted-foreground">{{s.label}}</p>
            <p className="mt-1 text-3xl font-bold">{{s.count != null ? s.count : '—'}}</p>
          </div>
        ))}}
      </div>

      <div className="rounded-xl border bg-card p-6">
        <h2 className="font-semibold mb-3">Recent {txn_label}s</h2>
        {{orders.length ? (
          <ul className="space-y-2 text-sm">{{orders.slice(0,5).map((o,i)=><li key={{i}} className="flex justify-between border-b pb-2"><span>{{o.id}}</span><span className="text-muted-foreground">{{o.status}}</span></li>)}}</ul>
        ) : <p className="text-sm text-muted-foreground">No {txn_label_lower}s yet.</p>}}
      </div>
    </div>
  );
}}
"""


# ── Prescription review page ─────────────────────────────────────────────────

_PRESCRIPTION_REVIEW_PAGE = """\
'use client';
// AUTO-GENERATED: Prescription Review — queue table + action panel
import * as React from 'react';

const STATUSES = ['pending', 'under_review', 'approved', 'rejected', 'clarification_required'];
const STATUS_COLORS = {{
  pending: 'bg-amber-100 text-amber-800',
  under_review: 'bg-blue-100 text-blue-800',
  approved: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-800',
  clarification_required: 'bg-orange-100 text-orange-800',
}};

export default function PrescriptionReviewPage() {{
  const [rows, setRows] = React.useState([]);
  const [selected, setSelected] = React.useState(null);
  const [filter, setFilter] = React.useState('pending');
  const [reviewNotes, setReviewNotes] = React.useState('');
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {{
    fetch('/api/prescriptions')
      .then((r) => r.json())
      .then((d) => setRows(Array.isArray(d.rows) ? d.rows : Array.isArray(d) ? d : []))
      .catch(() => {{}});
  }}, []);

  const visible = rows.filter((r) => !filter || r.review_status === filter);

  const updateStatus = (id, status) => {{
    setSaving(true);
    fetch('/api/prescriptions/' + id, {{
      method: 'PUT',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ review_status: status, review_notes: reviewNotes }}),
    }})
      .then((r) => r.json())
      .then(() => {{
        setRows((prev) => prev.map((r) => r._id === id ? {{ ...r, review_status: status }} : r));
        setSelected(null);
        setReviewNotes('');
      }})
      .catch(() => {{}})
      .finally(() => setSaving(false));
  }};

  return (
    <div className="flex gap-5 h-full">
      {{/* Left: prescription queue */}}
      <div className="flex-1 space-y-4 min-w-0">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Prescription Review</h1>
          <span className="rounded-full bg-amber-100 text-amber-800 text-xs font-semibold px-3 py-1.5">
            {{rows.filter((r) => r.review_status === 'pending').length}} Pending
          </span>
        </div>

        {{/* Status filter tabs */}}
        <div className="flex flex-wrap gap-2">
          {{['all', ...STATUSES].map((s) => (
            <button key={{s}} onClick={{() => setFilter(s === 'all' ? '' : s)}}
              className={{`rounded-full px-3 py-1 text-xs font-medium capitalize border transition ${{
                (filter === s || (s === 'all' && !filter)) ? 'bg-primary text-white border-primary' : 'border-slate-200 hover:border-primary/50'
              }}`}}>
              {{s.replace(/_/g, ' ')}}
            </button>
          ))}}
        </div>

        <div className="rounded-xl border bg-card overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Code</th>
                <th className="px-4 py-3 text-left font-medium">Patient</th>
                <th className="px-4 py-3 text-left font-medium">Doctor</th>
                <th className="px-4 py-3 text-left font-medium">Date</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {{visible.length === 0 ? (
                <tr><td colSpan="6" className="px-4 py-10 text-center text-muted-foreground">No prescriptions in this status.</td></tr>
              ) : visible.map((row) => (
                <tr key={{row._id}} onClick={{() => setSelected(row)}}
                  className={{`hover:bg-accent/30 cursor-pointer ${{selected?._id === row._id ? 'bg-accent/50' : ''}}`}}>
                  <td className="px-4 py-2.5 font-medium">{{row.prescription_code || (row._id || '').slice(-6) || '—'}}</td>
                  <td className="px-4 py-2.5">{{row.guest_name || '—'}}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{{row.doctor_name || '—'}}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{{row.prescription_date || '—'}}</td>
                  <td className="px-4 py-2.5">
                    <span className={{`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${{STATUS_COLORS[row.review_status] || 'bg-gray-100 text-gray-700'}}`}}>
                      {{(row.review_status || 'pending').replace(/_/g, ' ')}}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <button onClick={{(e) => {{ e.stopPropagation(); setSelected(row); }}}}
                      className="text-xs text-primary underline hover:text-primary/80">Review</button>
                  </td>
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      </div>

      {{/* Right: review panel */}}
      {{selected ? (
        <div className="w-72 shrink-0 rounded-xl border bg-card p-5 space-y-4 sticky top-0 h-fit max-h-screen overflow-y-auto">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm">Review Prescription</h2>
            <button onClick={{() => {{ setSelected(null); setReviewNotes(''); }}}} className="text-muted-foreground hover:text-foreground text-lg leading-none">✕</button>
          </div>
          <div className="space-y-1.5 text-sm">
            <div><span className="text-muted-foreground text-xs">Code</span><p className="font-medium">{{selected.prescription_code || '—'}}</p></div>
            <div><span className="text-muted-foreground text-xs">Patient</span><p>{{selected.guest_name || '—'}}</p></div>
            <div><span className="text-muted-foreground text-xs">Phone</span><p>{{selected.guest_phone || '—'}}</p></div>
            <div><span className="text-muted-foreground text-xs">Doctor</span><p>{{selected.doctor_name || '—'}}</p></div>
            <div><span className="text-muted-foreground text-xs">Date</span><p>{{selected.prescription_date || '—'}}</p></div>
          </div>
          {{selected.file_urls && (
            <div className="rounded-lg border bg-muted/30 h-28 flex items-center justify-center text-sm text-muted-foreground">
              📄 Prescription attached
            </div>
          )}}
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Review Notes</label>
            <textarea value={{reviewNotes}} onChange={{(e) => setReviewNotes(e.target.value)}} rows={{3}}
              className="w-full rounded-lg border px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Notes for patient or pharmacist..." />
          </div>
          <div className="space-y-2">
            <button onClick={{() => updateStatus(selected._id, 'approved')}} disabled={{saving}}
              className="w-full rounded-lg bg-emerald-600 text-white text-sm font-semibold py-2 hover:bg-emerald-700 disabled:opacity-50 transition">
              ✓ Approve
            </button>
            <button onClick={{() => updateStatus(selected._id, 'clarification_required')}} disabled={{saving}}
              className="w-full rounded-lg border border-amber-300 text-amber-700 text-sm font-semibold py-2 hover:bg-amber-50 disabled:opacity-50 transition">
              ⚠ Request Clarification
            </button>
            <button onClick={{() => updateStatus(selected._id, 'rejected')}} disabled={{saving}}
              className="w-full rounded-lg border border-red-300 text-red-700 text-sm font-semibold py-2 hover:bg-red-50 disabled:opacity-50 transition">
              ✕ Reject
            </button>
          </div>
        </div>
      ) : (
        <div className="w-72 shrink-0 rounded-xl border bg-muted/30 p-5 flex items-center justify-center text-sm text-muted-foreground">
          Click a prescription to review it
        </div>
      )}}
    </div>
  );
}}
"""


# ── Medicine management page ──────────────────────────────────────────────────

_MEDICINE_MGMT_PAGE = """\
'use client';
// AUTO-GENERATED: Medicine Management — searchable table with Rx badge
import * as React from 'react';
import Link from 'next/link';

export default function MedicineManagementPage() {{
  const [rows, setRows] = React.useState([]);
  const [search, setSearch] = React.useState('');
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {{
    fetch('/api/medicines')
      .then((r) => r.json())
      .then((d) => {{ setRows(Array.isArray(d.rows) ? d.rows : Array.isArray(d) ? d : []); setLoading(false); }})
      .catch(() => setLoading(false));
  }}, []);

  const visible = rows.filter((m) => {{
    const q = search.toLowerCase();
    return !q
      || (m.medicine_name || '').toLowerCase().includes(q)
      || (m.generic_name || '').toLowerCase().includes(q)
      || (m.barcode || '').includes(q);
  }});

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Medicine Management</h1>
        <Link href="/manage/medicines/new"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 transition">
          + Add Medicine
        </Link>
      </div>

      <div className="flex gap-3">
        <input value={{search}} onChange={{(e) => setSearch(e.target.value)}}
          placeholder="Search by name, generic name, or barcode..."
          className="flex-1 rounded-lg border px-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
      </div>

      {{loading ? (
        <div className="rounded-xl border bg-card p-12 text-center text-sm text-muted-foreground">Loading medicines…</div>
      ) : (
        <div className="rounded-xl border bg-card overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Medicine</th>
                <th className="px-4 py-3 text-left font-medium">Generic</th>
                <th className="px-4 py-3 text-left font-medium">Form</th>
                <th className="px-4 py-3 text-left font-medium">Strength</th>
                <th className="px-4 py-3 text-left font-medium">Price (LKR)</th>
                <th className="px-4 py-3 text-left font-medium">Reorder</th>
                <th className="px-4 py-3 text-left font-medium">Type</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {{visible.length === 0 ? (
                <tr><td colSpan="9" className="px-4 py-10 text-center text-muted-foreground">No medicines found. <Link href="/manage/medicines/new" className="text-primary underline">Add one.</Link></td></tr>
              ) : visible.map((m) => (
                <tr key={{m._id}} className="hover:bg-accent/30">
                  <td className="px-4 py-2.5 font-medium max-w-[160px] truncate">{{m.medicine_name || '—'}}</td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs max-w-[120px] truncate">{{m.generic_name || '—'}}</td>
                  <td className="px-4 py-2.5 capitalize">{{m.dosage_form || '—'}}</td>
                  <td className="px-4 py-2.5">{{m.strength || '—'}}</td>
                  <td className="px-4 py-2.5 font-medium">{{m.selling_price != null ? m.selling_price.toLocaleString() : '—'}}</td>
                  <td className="px-4 py-2.5">{{m.reorder_level ?? '—'}}</td>
                  <td className="px-4 py-2.5">
                    {{m.requires_prescription
                      ? <span className="rounded-full bg-amber-100 text-amber-800 text-xs px-2 py-0.5 font-medium">Rx</span>
                      : <span className="text-muted-foreground text-xs">OTC</span>}}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={{`rounded-full text-xs px-2 py-0.5 capitalize font-medium ${{m.status === 'active' ? 'bg-emerald-100 text-emerald-800' : m.status === 'discontinued' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}}`}}>
                      {{m.status || 'active'}}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-2">
                      <Link href={{`/manage/medicines/${{m._id}}/edit`}} className="text-xs text-primary underline">Edit</Link>
                      <Link href={{`/manage/medicines/${{m._id}}`}} className="text-xs text-muted-foreground underline">View</Link>
                    </div>
                  </td>
                </tr>
              ))}}
            </tbody>
          </table>
          {{visible.length > 0 && <p className="px-4 py-3 text-xs text-muted-foreground">{visible.length} medicine{{visible.length !== 1 ? 's' : ''}}</p>}}
        </div>
      )}}
    </div>
  );
}}
"""


# ── Inventory / batch management page ────────────────────────────────────────

_INVENTORY_PAGE = """\
'use client';
// AUTO-GENERATED: Inventory and Batch Management — stock table + low-stock/expiry alerts
import * as React from 'react';
import Link from 'next/link';

export default function InventoryPage() {{
  const [batches, setBatches] = React.useState([]);
  const [tab, setTab] = React.useState('all');
  const [loading, setLoading] = React.useState(true);
  const today = new Date().toISOString().split('T')[0];
  const soon = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  React.useEffect(() => {{
    fetch('/api/__BATCHCOLL__')
      .then((r) => r.json())
      .then((d) => {{ setBatches(Array.isArray(d.rows) ? d.rows : Array.isArray(d) ? d : []); setLoading(false); }})
      .catch(() => setLoading(false));
  }}, []);

  const lowStock = batches.filter((b) => (b.available_quantity ?? 0) <= (b.reorder_level ?? 10) && b.batch_status !== 'expired');
  const nearExpiry = batches.filter((b) => b.expiry_date && b.expiry_date <= soon && b.expiry_date >= today);
  const expired = batches.filter((b) => b.expiry_date && b.expiry_date < today);

  const visible = tab === 'low' ? lowStock : tab === 'expiry' ? nearExpiry : tab === 'expired' ? expired : batches;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Inventory & Batch Management</h1>
        <Link href="/admin/grn" className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 transition">
          + New GRN
        </Link>
      </div>

      {{/* Alert banners */}}
      {{lowStock.length > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <span className="text-xl">⚠️</span>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-amber-800 text-sm">{{lowStock.length}} Low Stock Alert{{lowStock.length !== 1 ? 's' : ''}}</p>
            <p className="text-xs text-amber-700">Items at or below reorder level. Raise purchase orders.</p>
          </div>
          <button onClick={{() => setTab('low')}} className="text-xs text-amber-700 underline whitespace-nowrap">View all</button>
        </div>
      )}}
      {{nearExpiry.length > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-orange-200 bg-orange-50 p-4">
          <span className="text-xl">📅</span>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-orange-800 text-sm">{{nearExpiry.length}} Near Expiry (within 90 days)</p>
            <p className="text-xs text-orange-700">Review and arrange disposal or return to supplier.</p>
          </div>
          <button onClick={{() => setTab('expiry')}} className="text-xs text-orange-700 underline whitespace-nowrap">View all</button>
        </div>
      )}}

      {{/* View tabs */}}
      <div className="flex flex-wrap gap-2">
        {{[['all', 'All Batches', batches.length], ['low', '⚠ Low Stock', lowStock.length], ['expiry', '📅 Near Expiry', nearExpiry.length], ['expired', '🚫 Expired', expired.length]].map(([key, label, count]) => (
          <button key={{key}} onClick={{() => setTab(key)}}
            className={{`rounded-full px-3 py-1.5 text-xs font-medium border transition ${{tab === key ? 'bg-primary text-white border-primary' : 'border-slate-200 hover:border-primary/50'}}`}}>
            {{label}} ({{count}})
          </button>
        ))}}
      </div>

      {{loading ? (
        <div className="rounded-xl border bg-card p-12 text-center text-sm text-muted-foreground">Loading inventory…</div>
      ) : (
        <div className="rounded-xl border bg-card overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Batch #</th>
                <th className="px-4 py-3 text-left font-medium">Expiry Date</th>
                <th className="px-4 py-3 text-left font-medium">Available Qty</th>
                <th className="px-4 py-3 text-left font-medium">Reserved</th>
                <th className="px-4 py-3 text-left font-medium">Selling Price</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {{visible.length === 0 ? (
                <tr><td colSpan="7" className="px-4 py-10 text-center text-muted-foreground">No batches in this view.</td></tr>
              ) : visible.map((b) => (
                <tr key={{b._id}} className="hover:bg-accent/30">
                  <td className="px-4 py-2.5 font-medium">{{b.batch_number || (b._id || '').slice(-6) || '—'}}</td>
                  <td className={{`px-4 py-2.5 ${{b.expiry_date < today ? 'text-red-600 font-semibold' : b.expiry_date <= soon ? 'text-orange-600' : ''}}`}}>
                    {{b.expiry_date || '—'}}
                  </td>
                  <td className={{`px-4 py-2.5 font-medium ${{(b.available_quantity ?? 0) <= (b.reorder_level ?? 10) ? 'text-amber-600' : ''}}`}}>
                    {{b.available_quantity ?? '—'}}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{{b.reserved_quantity ?? '—'}}</td>
                  <td className="px-4 py-2.5">{{b.selling_price != null ? `LKR ${{b.selling_price.toLocaleString()}}` : '—'}}</td>
                  <td className="px-4 py-2.5">
                    <span className={{`rounded-full text-xs px-2 py-0.5 capitalize font-medium ${{b.batch_status === 'active' ? 'bg-emerald-100 text-emerald-800' : b.batch_status === 'expired' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700'}}`}}>
                      {{b.batch_status || 'active'}}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-2">
                      <Link href={{`/manage/__BATCHCOLL__/${{b._id}}/edit`}} className="text-xs text-primary underline">Adjust</Link>
                      <Link href={{`/manage/__BATCHCOLL__/${{b._id}}`}} className="text-xs text-muted-foreground underline">View</Link>
                    </div>
                  </td>
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      )}}
    </div>
  );
}}
"""


# ── CRUD management page variants ────────────────────────────────────────────
# Three layouts: table (default), card-grid, split-pane. Selected per entity
# by the genome's crud_layout; the SRS page generator picks the right one.
# All share the same COLLECTION / DISPLAY_FIELDS / FORM_FIELDS / QUICK_ACTIONS
# constants baked in at generation time.

_CRUD_CARD_GRID_PAGE = """\
'use client';
// AUTO-GENERATED card-grid: {page_name}
// SRS roles: {roles_comment}
import * as React from 'react';

const COLLECTION = '{collection}';
const PAGE_TITLE = '{page_name_jsx}';
const CREATE_LABEL = '{create_label}';
const DISPLAY_FIELDS = {display_fields_json};
const FORM_FIELDS = {form_fields_json};
const QUICK_ACTIONS = {funcs_json};
const STATUS_CLR = {{
  active:'bg-emerald-100 text-emerald-800', inactive:'bg-gray-100 text-gray-600',
  pending:'bg-amber-100 text-amber-800', approved:'bg-emerald-100 text-emerald-800',
  rejected:'bg-red-100 text-red-700', completed:'bg-blue-100 text-blue-800',
}};

export default function ManagementPage() {{
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState('');
  const [formOpen, setFormOpen] = React.useState(false);
  const [editRow, setEditRow] = React.useState(null);
  const [form, setForm] = React.useState({{}});
  const [saving, setSaving] = React.useState(false);
  const API = '/api/' + COLLECTION;

  React.useEffect(() => {{
    fetch(API).then((r) => r.json())
      .then((d) => {{ setRows(Array.isArray(d.rows)?d.rows:Array.isArray(d)?d:[]); setLoading(false); }})
      .catch(() => setLoading(false));
  }}, []);

  const visible = React.useMemo(() =>
    rows.filter((r) => DISPLAY_FIELDS.some((f) => String(r[f.key]||'').toLowerCase().includes(search.toLowerCase()))),
    [rows, search]);

  const openCreate = () => {{ setEditRow(null); setForm(Object.fromEntries(FORM_FIELDS.map((f) => [f.key, f.options?.[0]||'']))); setFormOpen(true); }};
  const openEdit   = (r) => {{ setEditRow(r); setForm({{...r}}); setFormOpen(true); }};
  const closeForm  = () => {{ setFormOpen(false); setEditRow(null); }};
  const save = async () => {{
    setSaving(true);
    try {{
      const url = editRow ? API+'/'+editRow._id : API;
      const method = editRow ? 'PUT' : 'POST';
      const res = await fetch(url, {{method, headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(form)}});
      const data = await res.json();
      setRows((p) => editRow ? p.map((r) => r._id===editRow._id?data:r) : [data,...p]);
      closeForm();
    }} catch(e) {{}} finally {{ setSaving(false); }}
  }};
  const del = async (id) => {{
    if (!window.confirm('Delete this record?')) return;
    await fetch(API+'/'+id, {{method:'DELETE'}});
    setRows((p) => p.filter((r) => r._id!==id));
  }};
  const badge = (v) => <span className={{STATUS_CLR[String(v||'').toLowerCase()]||'bg-gray-100 text-gray-600'}}> className="rounded-full px-2.5 py-0.5 text-xs font-medium">{{''+v}}</span>;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{{PAGE_TITLE}}</h1>
          <p className="text-sm text-muted-foreground">{{visible.length}} record{{visible.length!==1?'s':''}}</p>
        </div>
        <button onClick={{openCreate}} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">+ {{CREATE_LABEL}}</button>
      </div>
      <input type="search" placeholder="Search…" value={{search}} onChange={{(e)=>setSearch(e.target.value)}}
        className="w-full max-w-xs rounded-lg border border-input bg-background px-3 py-2 text-sm" />
      {{loading && <p className="text-sm text-muted-foreground">Loading…</p>}}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {{visible.map((row) => (
          <div key={{row._id}} className="rounded-xl border bg-card p-4 shadow-sm hover:shadow-md transition">
            <div className="mb-3 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-semibold">{{String(row[DISPLAY_FIELDS[0]?.key]||'—')}}</p>
                {{DISPLAY_FIELDS[1] && <p className="mt-0.5 truncate text-xs text-muted-foreground">{{String(row[DISPLAY_FIELDS[1].key]||'')}}</p>}}
              </div>
              {{DISPLAY_FIELDS.find((f)=>f.key==='status') && badge(row.status)}}
            </div>
            {{DISPLAY_FIELDS.slice(2).map((f)=>(
              <div key={{f.key}} className="mt-1 flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{{f.label}}</span>
                <span>{{String(row[f.key]||'—')}}</span>
              </div>
            ))}}
            <div className="mt-4 flex gap-2 border-t pt-3">
              <button onClick={{()=>openEdit(row)}} className="flex-1 rounded-md border px-2 py-1 text-xs font-medium hover:bg-muted">Edit</button>
              <button onClick={{()=>del(row._id)}} className="rounded-md border border-destructive/30 px-2 py-1 text-xs text-destructive hover:bg-destructive/10">Delete</button>
            </div>
          </div>
        ))}}
        {{!loading && visible.length===0 && <p className="col-span-full text-center text-sm text-muted-foreground py-12">No records found.</p>}}
      </div>
      {{formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-background p-6 shadow-2xl">
            <h2 className="mb-4 font-semibold">{{editRow?'Edit':'New'}} {{CREATE_LABEL}}</h2>
            <div className="space-y-3">
              {{FORM_FIELDS.map((f) => (
                <div key={{f.key}} className="space-y-1">
                  <label className="text-sm font-medium">{{f.label}}</label>
                  {{f.type==='select'
                    ? <select className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" value={{form[f.key]||''}} onChange={{(e)=>setForm((p)=>({...p,[f.key]:e.target.value}))}}>
                        {{(f.options||[]).map((o)=><option key={{o}} value={{o}}>{{o}}</option>)}}
                      </select>
                    : <input type={{f.type||'text'}} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                        value={{form[f.key]||''}} onChange={{(e)=>setForm((p)=>({...p,[f.key]:e.target.value}))}} />
                  }}
                </div>
              ))}}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={{closeForm}} className="rounded-lg border px-4 py-2 text-sm">Cancel</button>
              <button onClick={{save}} disabled={{saving}} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-60">{{saving?'Saving…':'Save'}}</button>
            </div>
          </div>
        </div>
      )}}
      {{QUICK_ACTIONS.length>0 && (
        <details className="rounded-xl border bg-muted/30 p-4">
          <summary className="cursor-pointer text-sm font-medium">Quick Actions ({{{'{'}QUICK_ACTIONS.length{'}'}}})</summary>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {{QUICK_ACTIONS.map((a)=><li key={{a}} className="rounded-lg border bg-background px-3 py-2 text-sm">{{a}}</li>)}}
          </ul>
        </details>
      )}}
    </div>
  );
}}
"""

_CRUD_SPLIT_PANE_PAGE = """\
'use client';
// AUTO-GENERATED split-pane: {page_name}
// SRS roles: {roles_comment}
import * as React from 'react';

const COLLECTION = '{collection}';
const PAGE_TITLE = '{page_name_jsx}';
const CREATE_LABEL = '{create_label}';
const DISPLAY_FIELDS = {display_fields_json};
const FORM_FIELDS = {form_fields_json};
const QUICK_ACTIONS = {funcs_json};
const STATUS_CLR = {{
  active:'bg-emerald-100 text-emerald-800', inactive:'bg-gray-100 text-gray-600',
  pending:'bg-amber-100 text-amber-800', approved:'bg-emerald-100 text-emerald-800',
  rejected:'bg-red-100 text-red-700', completed:'bg-blue-100 text-blue-800',
}};

export default function ManagementPage() {{
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState('');
  const [selected, setSelected] = React.useState(null);
  const [editing, setEditing] = React.useState(false);
  const [form, setForm] = React.useState({{}});
  const [saving, setSaving] = React.useState(false);
  const API = '/api/' + COLLECTION;

  React.useEffect(() => {{
    fetch(API).then((r) => r.json())
      .then((d) => {{ const arr=Array.isArray(d.rows)?d.rows:Array.isArray(d)?d:[]; setRows(arr); if(arr[0]) setSelected(arr[0]); setLoading(false); }})
      .catch(() => setLoading(false));
  }}, []);

  const visible = React.useMemo(() =>
    rows.filter((r) => DISPLAY_FIELDS.some((f) => String(r[f.key]||'').toLowerCase().includes(search.toLowerCase()))),
    [rows, search]);

  const startEdit = () => {{ setForm({{...selected}}); setEditing(true); }};
  const save = async () => {{
    setSaving(true);
    try {{
      const res = await fetch(API+'/'+selected._id, {{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(form)}});
      const data = await res.json();
      setRows((p)=>p.map((r)=>r._id===selected._id?data:r));
      setSelected(data); setEditing(false);
    }} catch(e) {{}} finally {{ setSaving(false); }}
  }};
  const del = async () => {{
    if(!window.confirm('Delete this record?')) return;
    await fetch(API+'/'+selected._id,{{method:'DELETE'}});
    const next = rows.filter((r)=>r._id!==selected._id);
    setRows(next); setSelected(next[0]||null); setEditing(false);
  }};
  const addNew = async () => {{
    const blank = Object.fromEntries(FORM_FIELDS.map((f)=>[f.key,f.options?.[0]||'']));
    setSaving(true);
    try {{
      const res = await fetch(API,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(blank)}});
      const data = await res.json();
      setRows((p)=>[data,...p]); setSelected(data); setEditing(true); setForm({{...data}});
    }} catch(e){{}} finally{{setSaving(false);}};
  }};
  const badge = (v) => <span className={{(STATUS_CLR[String(v||'').toLowerCase()]||'bg-gray-100 text-gray-600')+' rounded-full px-2.5 py-0.5 text-xs font-medium'}}>{{''+v}}</span>;

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-0 overflow-hidden rounded-xl border bg-background shadow-sm">
      {{/* List panel */}}
      <div className="flex w-72 shrink-0 flex-col border-r">
        <div className="flex items-center justify-between border-b p-3">
          <span className="font-semibold text-sm">{{PAGE_TITLE}}</span>
          <button onClick={{addNew}} className="rounded-md bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground">+ New</button>
        </div>
        <div className="border-b p-2">
          <input type="search" placeholder="Search…" value={{search}} onChange={{(e)=>setSearch(e.target.value)}
            className="w-full rounded-md border border-input bg-muted px-2.5 py-1.5 text-xs" />
        </div>
        <ul className="flex-1 overflow-y-auto">
          {{loading && <li className="p-4 text-xs text-muted-foreground">Loading…</li>}}
          {{visible.map((row)=>(
            <li key={{row._id}} onClick={{()=>{{setSelected(row);setEditing(false);}}}}
              className={{'flex cursor-pointer items-center gap-2.5 border-b px-3 py-2.5 text-sm transition '+(selected?._id===row._id?'bg-primary/8 font-medium':'hover:bg-muted')}}>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{{String(row[DISPLAY_FIELDS[0]?.key]||'—')}}</p>
                {{DISPLAY_FIELDS[1]&&<p className="truncate text-xs text-muted-foreground">{{String(row[DISPLAY_FIELDS[1].key]||'')}}</p>}}
              </div>
            </li>
          ))}}
        </ul>
      </div>
      {{/* Detail panel */}}
      <div className="flex flex-1 flex-col overflow-hidden">
        {{selected ? (
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b p-4">
              <div>
                <h2 className="font-semibold">{{String(selected[DISPLAY_FIELDS[0]?.key]||'Record')}}</h2>
                {{selected.status && badge(selected.status)}}
              </div>
              <div className="flex gap-2">
                {{!editing && <button onClick={{startEdit}} className="rounded-lg border px-3 py-1.5 text-xs font-medium">Edit</button>}}
                {{!editing && <button onClick={{del}} className="rounded-lg border border-destructive/30 px-3 py-1.5 text-xs text-destructive">Delete</button>}}
                {{editing && <button onClick={{()=>setEditing(false)}} className="rounded-lg border px-3 py-1.5 text-xs">Cancel</button>}}
                {{editing && <button onClick={{save}} disabled={{saving}} className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground disabled:opacity-60">{{saving?'Saving…':'Save'}}</button>}}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {{editing ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  {{FORM_FIELDS.map((f)=>(
                    <div key={{f.key}} className="space-y-1.5">
                      <label className="text-sm font-medium">{{f.label}}</label>
                      {{f.type==='select'
                        ?<select className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" value={{form[f.key]||''}} onChange={{(e)=>setForm((p)=>({...p,[f.key]:e.target.value}))}}>{{(f.options||[]).map((o)=><option key={{o}} value={{o}}>{{o}}</option>)}}</select>
                        :<input type={{f.type||'text'}} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" value={{form[f.key]||''}} onChange={{(e)=>setForm((p)=>({...p,[f.key]:e.target.value}))}} />
                      }}
                    </div>
                  ))}}
                </div>
              ) : (
                <dl className="grid gap-3 sm:grid-cols-2">
                  {{DISPLAY_FIELDS.map((f)=>(
                    <div key={{f.key}} className="rounded-lg border bg-muted/30 p-3">
                      <dt className="text-xs text-muted-foreground">{{f.label}}</dt>
                      <dd className="mt-1 text-sm font-medium">{{String(selected[f.key]||'—')}}</dd>
                    </div>
                  ))}}
                </dl>
              )}}
              {{QUICK_ACTIONS.length>0&&(
                <details className="mt-5 rounded-xl border p-3">
                  <summary className="cursor-pointer text-sm font-medium">Actions</summary>
                  <ul className="mt-2 space-y-1">
                    {{QUICK_ACTIONS.map((a)=><li key={{a}} className="rounded-md border bg-background px-3 py-1.5 text-xs">{{a}}</li>)}}
                  </ul>
                </details>
              )}}
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Select a record</div>
        )}}
      </div>
    </div>
  );
}}
"""

# ── Generic CRUD management page (table layout — default) ─────────────────────
# Replaces the old function-card admin section. Renders a searchable table with
# inline create / edit modal and delete. Collection, display columns, and form
# fields are baked in at generation time from the data model + SRS.

_CRUD_MGMT_PAGE = """\
'use client';
// AUTO-GENERATED: {page_name}
// SRS roles: {roles_comment}
import * as React from 'react';

const COLLECTION = '{collection}';
const PAGE_TITLE = '{page_name_jsx}';
const CREATE_LABEL = '{create_label}';
const DISPLAY_FIELDS = {display_fields_json};
const FORM_FIELDS = {form_fields_json};
const STATUS_CLR = {{
  active: 'bg-emerald-100 text-emerald-800',
  inactive: 'bg-gray-100 text-gray-600',
  pending: 'bg-amber-100 text-amber-800',
  approved: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-700',
  cancelled: 'bg-red-100 text-red-700',
  completed: 'bg-blue-100 text-blue-800',
  open: 'bg-blue-100 text-blue-800',
  closed: 'bg-gray-100 text-gray-600',
  deactivated: 'bg-gray-100 text-gray-600',
}};

export default function ManagementPage() {{
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState('');
  const [formOpen, setFormOpen] = React.useState(false);
  const [editRow, setEditRow] = React.useState(null);
  const [form, setForm] = React.useState({{}});
  const [saving, setSaving] = React.useState(false);

  const API = '/api/' + COLLECTION;

  React.useEffect(() => {{
    fetch(API)
      .then((r) => r.json())
      .then((d) => {{ setRows(Array.isArray(d.rows) ? d.rows : Array.isArray(d) ? d : []); setLoading(false); }})
      .catch(() => setLoading(false));
  }}, []);

  const visible = React.useMemo(() => {{
    if (!search) return rows;
    const q = search.toLowerCase();
    return rows.filter((r) => Object.values(r).some((v) => String(v ?? '').toLowerCase().includes(q)));
  }}, [rows, search]);

  function openCreate() {{ setEditRow(null); setForm({{}}); setFormOpen(true); }}
  function openEdit(row) {{ setEditRow(row); setForm({{ ...row }}); setFormOpen(true); }}
  function closeForm() {{ setFormOpen(false); setEditRow(null); setForm({{}}); }}

  function save() {{
    setSaving(true);
    const method = editRow ? 'PUT' : 'POST';
    const url = editRow ? `${{API}}/${{editRow._id}}` : API;
    fetch(url, {{ method, headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(form) }})
      .then((r) => r.json())
      .then((saved) => {{
        if (editRow) setRows((p) => p.map((r) => r._id === saved._id ? saved : r));
        else setRows((p) => [saved, ...p]);
        closeForm();
      }})
      .catch(() => {{}})
      .finally(() => setSaving(false));
  }}

  function del(id) {{
    if (!window.confirm('Delete this record?')) return;
    fetch(`${{API}}/${{id}}`, {{ method: 'DELETE' }})
      .then(() => setRows((p) => p.filter((r) => r._id !== id)))
      .catch(() => {{}});
  }}

  function exportCsv() {{
    const cols = DISPLAY_FIELDS.map((f) => f.key);
    const head = DISPLAY_FIELDS.map((f) => f.label).join(',');
    const lines = visible.map((r) => cols.map((k) => JSON.stringify(r[k] ?? '')).join(','));
    const csv = [head].concat(lines).join(String.fromCharCode(10));
    const blob = new Blob([csv], {{ type: 'text/csv' }});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = COLLECTION + '.csv';
    a.click();
  }}

  function renderCell(row, key) {{
    const v = row[key];
    if (v == null || v === '') return <span className="text-muted-foreground">—</span>;
    const s = String(v);
    const cls = STATUS_CLR[s.toLowerCase()];
    if (cls) return <span className={{`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${{cls}}`}}>{{s}}</span>;
    if (s.length > 60) return <span title={{s}}>{{s.slice(0, 57)}}…</span>;
    return s;
  }}

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{{PAGE_TITLE}}</h1>
          <p className="text-sm text-muted-foreground">{{rows.length}} record{{rows.length !== 1 ? 's' : ''}}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={{exportCsv}}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-accent transition">Export CSV</button>
          <button onClick={{openCreate}}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 transition">
            + {{CREATE_LABEL}}
          </button>
        </div>
      </div>

      <div className="max-w-xs">
        <input
          value={{search}}
          onChange={{(e) => setSearch(e.target.value)}}
          placeholder={{`Search ${{PAGE_TITLE.toLowerCase()}}…`}}
          className="w-full rounded-lg border px-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      <div className="rounded-xl border bg-card overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              {{DISPLAY_FIELDS.map((f) => (
                <th key={{f.key}} className="px-4 py-3 text-left font-medium">{{f.label}}</th>
              ))}}
              <th className="px-4 py-3 text-left font-medium w-24">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {{loading ? (
              <tr><td colSpan={{DISPLAY_FIELDS.length + 1}} className="px-4 py-12 text-center text-sm text-muted-foreground">Loading…</td></tr>
            ) : visible.length === 0 ? (
              <tr><td colSpan={{DISPLAY_FIELDS.length + 1}} className="px-4 py-12 text-center text-sm text-muted-foreground">
                No records yet.{{' '}}
                <button onClick={{openCreate}} className="text-primary underline">Create the first →</button>
              </td></tr>
            ) : visible.map((row) => (
              <tr key={{row._id}} className="hover:bg-accent/30">
                {{DISPLAY_FIELDS.map((f) => (
                  <td key={{f.key}} className="px-4 py-2.5">{{renderCell(row, f.key)}}</td>
                ))}}
                <td className="px-4 py-2.5">
                  <div className="flex gap-3">
                    <button onClick={{() => openEdit(row)}} className="text-xs text-primary underline">Edit</button>
                    <button onClick={{() => del(row._id)}} className="text-xs text-red-500 underline">Delete</button>
                  </div>
                </td>
              </tr>
            ))}}
          </tbody>
        </table>
        {{visible.length > 0 && (
          <p className="border-t px-4 py-3 text-xs text-muted-foreground">
            {{visible.length}} of {{rows.length}} record{{rows.length !== 1 ? 's' : ''}}
          </p>
        )}}
      </div>

      {{formOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={{(e) => e.target === e.currentTarget && closeForm()}}
        >
          <div className="w-full max-w-lg rounded-xl bg-white dark:bg-card shadow-2xl">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2 className="font-semibold">{{editRow ? 'Edit' : 'Create'}} {{CREATE_LABEL.replace('New ', '')}}</h2>
              <button onClick={{closeForm}} className="text-xl leading-none text-muted-foreground hover:text-foreground">✕</button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto px-6 py-5 space-y-4">
              {{FORM_FIELDS.map((f) => (
                <div key={{f.key}}>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">{{f.label}}</label>
                  {{f.type === 'textarea' ? (
                    <textarea rows={{3}} value={{form[f.key] || ''}}
                      onChange={{(e) => setForm((p) => ({{ ...p, [f.key]: e.target.value }}))}}
                      placeholder={{f.label}}
                      className="w-full resize-none rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                  ) : f.options?.length ? (
                    <select value={{form[f.key] || ''}}
                      onChange={{(e) => setForm((p) => ({{ ...p, [f.key]: e.target.value }}))}}
                      className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                      <option value="">Select {{f.label}}…</option>
                      {{(f.options || []).map((o) => <option key={{o}} value={{o}}>{{o}}</option>)}}
                    </select>
                  ) : (
                    <input type={{f.type || 'text'}} value={{form[f.key] || ''}}
                      onChange={{(e) => setForm((p) => ({{ ...p, [f.key]: e.target.value }}))}}
                      placeholder={{f.label}}
                      className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                  )}}
                </div>
              ))}}
            </div>
            <div className="flex justify-end gap-2 border-t px-6 py-4">
              <button onClick={{closeForm}} className="rounded-lg border px-4 py-2 text-sm">Cancel</button>
              <button onClick={{save}} disabled={{saving}}
                className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition">
                {{saving ? 'Saving…' : editRow ? 'Save Changes' : 'Create'}}
              </button>
            </div>
          </div>
        </div>
      )}}
    </div>
  );
}}
"""


# ── Stub page (for anything else) ─────────────────────────────────────────────

_STUB_PAGE = """\
'use client';
// AUTO-GENERATED: {page_name}
// SRS roles: {roles_comment}
import * as React from 'react';

const PAGE_FUNCTIONS = {funcs_json};

export default function Page() {{
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{page_name_jsx}</h1>
      {{PAGE_FUNCTIONS.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {{PAGE_FUNCTIONS.map((fn, i) => (
            <div key={{i}} className="rounded-xl border bg-card p-4">
              <p className="text-sm font-medium">{{fn}}</p>
            </div>
          ))}}
        </div>
      )}}
    </div>
  );
}}
"""

# ── Reports API route stub ────────────────────────────────────────────────────

_REPORTS_API = """\
// AUTO-GENERATED: Reports API stub — delegates to per-collection list endpoints.
import { NextResponse } from 'next/server';
import { listDocs } from '@/lib/orm';

const REPORT_COLLECTIONS = {coll_map};

export const dynamic = 'force-dynamic';

export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const report = searchParams.get('report') || '';
  const from = searchParams.get('from');
  const to = searchParams.get('to');

  const coll = REPORT_COLLECTIONS[report];
  if (!coll) return NextResponse.json({ rows: [] });

  const result = await listDocs(coll, { limit: 200 });
  let rows = result.rows || [];

  if (from || to) {
    rows = rows.filter((r) => {
      const d = r.createdAt || r.date || r.sale_date || '';
      if (from && d < from) return false;
      if (to && d > to) return false;
      return true;
    });
  }

  return NextResponse.json({ rows });
}
"""


# ── Notification model + API ──────────────────────────────────────────────────

_NOTIF_MODEL = """\
// AUTO-GENERATED: Notification descriptor (from SRS notification_requirements).
export const Notification = {
  name: 'Notification',
  label: 'Notifications',
  collection: 'notifications',
  fields: [
    { name: 'event', label: 'Event', type: 'text' },
    { name: 'message', label: 'Message', type: 'textarea' },
    { name: 'recipientRole', label: 'Recipient Role', type: 'text' },
    { name: 'recipientId', label: 'Recipient', type: 'text' },
    { name: 'channel', label: 'Channel', type: 'enum', enum: ['email', 'sms', 'in-app'] },
    { name: 'read', label: 'Read', type: 'boolean' },
    { name: 'createdAt', label: 'Created At', type: 'datetime' },
  ],
  refs: [],
  indexes: ['recipientId', 'recipientRole', 'read'],
  events: {events_json},
};
export default Notification;
"""

_NOTIF_SERVICE = """\
// AUTO-GENERATED: Notification dispatch service.
import { createDoc } from '@/lib/orm';

const NOTIFICATION_EVENTS = {events_json};

export async function dispatchNotification(event, { recipientId, recipientRole, message, channel = 'in-app' } = {}) {
  const def = NOTIFICATION_EVENTS.find((e) => e.event === event);
  if (!def) return;
  const msg = message || def.message || def.event;
  const roles = recipientRole ? [recipientRole] : (def.recipients || []);
  for (const role of (roles.length ? roles : ['Admin'])) {
    await createDoc('notifications', {
      event,
      message: msg,
      recipientRole: role,
      recipientId: recipientId || null,
      channel,
      read: false,
    }).catch(() => {});
  }
}

export async function markRead(id) {
  const { updateDoc } = await import('@/lib/orm');
  return updateDoc('notifications', id, { read: true });
}
"""

_NOTIF_API = """\
// AUTO-GENERATED: Notifications API — list + mark-read.
import { NextResponse } from 'next/server';
import { listDocs } from '@/lib/orm';
import { roleFromRequest } from '@/lib/apiAuth';

export const dynamic = 'force-dynamic';

export async function GET(req) {
  const role = roleFromRequest(req);
  const { searchParams } = new URL(req.url);
  const page = Number(searchParams.get('page') || 1);
  const filter = {};
  if (role) filter.recipientRole = role;
  const result = await listDocs('notifications', { filter, page, limit: 50 });
  return NextResponse.json(result);
}
"""


# ── collection slug helpers ───────────────────────────────────────────────────

_ROUTE_TO_COLLECTION = {
    "medicines": "medicines", "medicine": "medicines",
    "prescriptions": "prescriptions", "prescription": "prescriptions",
    "inventory": "inventorystocks", "stock": "inventorystocks",
    "suppliers": "suppliers", "supplier": "suppliers",
    "orders": "onlineorders", "online-orders": "onlineorders",
    "purchase-orders": "purchaseorders", "purchaseorders": "purchaseorders",
    "grn": "goodsreceivednotes",
    "billing": "possales", "pos": "possales",
    "returns": "returns", "return": "returns",
    "customers": "customers", "customer": "customers",
    "staff": "staffprofiles",
    "catalog": "medicinecategories",
    # generic keys
    "products": "products", "sales": "sales", "invoices": "invoices",
    "rooms": "rooms", "reservations": "reservations",
    "vehicles": "vehicles", "students": "students",
    "branches": "branches", "stores": "stores",
}


def _infer_manage_href(route: str, dm: dict) -> str:
    """Map SRS route to the closest /manage/{collection} link."""
    slug = route.strip("/").split("/")[-1]
    # try exact match from our mapping
    coll = _ROUTE_TO_COLLECTION.get(slug)
    if coll:
        return f"/manage/{coll}"
    # try matching against the data model's entity collections
    if dm:
        for e in dm.get("entities", []):
            ecoll = e.get("collection", "")
            if slug in ecoll or ecoll.startswith(slug[:4]):
                return f"/manage/{ecoll}"
    # no match → return empty (page shows functions only)
    return ""


def _is_pos_route(route: str) -> bool:
    return bool(re.search(r"/pos\b", route, re.I))


def _is_report_route(route: str) -> bool:
    return bool(re.search(r"/report", route, re.I))


def _is_customer_dash(route: str) -> bool:
    return bool(re.search(r"/customer[^/]*/dashboard", route, re.I))


def _is_admin_dash(route: str) -> bool:
    return bool(re.search(r"/admin[^/]*/dashboard", route, re.I)) or route.strip("/") == "admin/dashboard"


# ── domain-entity resolver ────────────────────────────────────────────────────
# POS / customer-portal / inventory pages are domain-shaped but were originally
# hardcoded to pharmacy (medicines / prescriptions / medicine batches). These
# helpers derive the right entity + collection from the planned data model so the
# SAME templates work for any domain (hotel sells MenuItems via PosOrders, retail
# sells Products via Sales, vehicle sells SpareParts via PosSales, etc).

def _pick_entity(dm, keywords, exclude=()):
    for kw in keywords:
        for e in (dm or {}).get("entities", []) or []:
            nm = (e.get("name") or "").lower()
            if kw in nm and not any(x in nm for x in exclude):
                return e
    return None


def _display_field(ent):
    if ent:
        for f in ent.get("fields", []) or []:
            n = (f.get("name") or "").lower()
            if n in ("name", "title") or n.endswith("_name") or n.endswith("_title"):
                return f.get("name")
    return "name"


def _singular_label(s):
    s = str(s or "").strip()
    return s[:-1] if s.endswith("s") and not s.endswith("ss") else s


def _resolve_domain(dm):
    """Derive POS catalog / sale, customer-transaction, and batch entities."""
    # NB: exclude tokens are substring-matched, so avoid short ones that collide
    # with wanted names (e.g. "line" is inside "onLINEorder").
    _TXN = ("item", "detail")
    cat = (_pick_entity(dm, ["menuitem", "sparepart", "product", "medicine", "dish", "good"],
                        exclude=("order", "sale", "cart", "invoice", "movement", "stock", "return",
                                 "payment", "category", "variant", "brand"))
           or _pick_entity(dm, ["service", "catalog"], exclude=("order", "sale", "movement", "stock"))
           or _pick_entity(dm, ["room", "vehicle", "course", "book", "property", "listing"]))
    sale = (_pick_entity(dm, ["possale", "posorder"], exclude=_TXN)
            or _pick_entity(dm, ["sale", "order", "invoice", "bill", "transaction"], exclude=_TXN + ("online",)))
    txn = (_pick_entity(dm, ["reservation", "booking", "appointment", "enrollment"], exclude=_TXN)
           or _pick_entity(dm, ["onlineorder", "inquiry", "rental", "registration", "order", "sale"],
                           exclude=_TXN + ("purchase", "supplier", "grn", "goods", "received")))
    batch = _pick_entity(dm, ["batch"], exclude=("movement",))

    def coll(e, d):
        return (e or {}).get("collection") or d

    def lab(e, d):
        return _singular_label((e or {}).get("label") or (e or {}).get("name") or d)

    return {
        "catalog_collection": coll(cat, "records"),
        "catalog_label": lab(cat, "Item"),
        "catalog_name_field": _display_field(cat),
        "sale_collection": coll(sale, txn and txn.get("collection") or "records"),
        "txn_collection": coll(txn, coll(sale, "records")),
        "txn_label": lab(txn, "Order"),
        "has_batch": bool(batch),
        "batch_collection": coll(batch, "records"),
    }


# ── CRUD context derivation ───────────────────────────────────────────────────

_SKIP_FIELDS = {"_id", "id", "password", "password_hash", "created_at", "updated_at",
                "createdAt", "updatedAt", "deleted_at", "deletedAt", "__v"}


def _derive_crud_context(route: str, page_name: str, dm: dict, functions: list) -> dict:
    """Return collection, display_fields, form_fields, create_label for a CRUD page."""
    slug = route.strip("/").split("/")[-1]

    # 1. Collection: static map → entity match → slug fallback
    collection = _ROUTE_TO_COLLECTION.get(slug, "")
    if not collection and dm:
        slug_lc = slug.lower().replace("-", "")
        for e in (dm.get("entities") or []):
            ecoll = (e.get("collection") or "").lower()
            ename = (e.get("name") or "").lower()
            if slug_lc in ecoll or ecoll.startswith(slug_lc[:4]) or slug_lc in ename:
                collection = e.get("collection", "")
                break
    if not collection:
        collection = re.sub(r"[^a-z0-9]", "", slug.lower()) or "records"

    # 2. Find entity
    entity = None
    if dm:
        coll_lc = collection.lower()
        for e in (dm.get("entities") or []):
            if (e.get("collection") or "").lower() == coll_lc:
                entity = e
                break
        if not entity:
            # partial match
            for e in (dm.get("entities") or []):
                if coll_lc in (e.get("collection") or "").lower():
                    entity = e
                    break

    # 3. Build display fields (first 5 non-meta fields)
    display_fields = []
    form_fields = []
    if entity:
        for f in (entity.get("fields") or []):
            fname = f.get("name", "")
            if not fname or fname in _SKIP_FIELDS:
                continue
            flabel = fname.replace("_", " ").title()
            ftype_raw = (f.get("type") or "text").lower()
            # display
            if len(display_fields) < 5:
                display_fields.append({"key": fname, "label": flabel})
            # form
            if len(form_fields) < 8:
                if ftype_raw in ("text", "string") and "description" in fname.lower():
                    ftype = "textarea"
                elif ftype_raw in ("number", "int", "float", "decimal", "integer"):
                    ftype = "number"
                elif "email" in fname.lower():
                    ftype = "email"
                elif "phone" in fname.lower():
                    ftype = "tel"
                elif ftype_raw in ("date",):
                    ftype = "date"
                elif ftype_raw in ("datetime",):
                    ftype = "datetime-local"
                elif ftype_raw in ("enum", "select"):
                    ftype = "select"
                else:
                    ftype = "text"
                fd = {"key": fname, "label": flabel, "type": ftype}
                if ftype == "select" and f.get("enum"):
                    fd["options"] = list(f["enum"])[:8]
                form_fields.append(fd)

    # fallbacks
    if not display_fields:
        display_fields = [
            {"key": "name", "label": "Name"},
            {"key": "status", "label": "Status"},
            {"key": "createdAt", "label": "Created"},
        ]
    if not form_fields:
        first = page_name.split()[0] if page_name else "Record"
        form_fields = [
            {"key": "name", "label": f"{first} Name", "type": "text"},
            {"key": "status", "label": "Status", "type": "select",
             "options": ["active", "inactive"]},
            {"key": "notes", "label": "Notes", "type": "textarea"},
        ]

    # 4. Entity label for create button
    ent_label = ""
    if entity:
        ent_label = (entity.get("label") or entity.get("name") or "").strip()
    if not ent_label:
        ent_label = _singular_label(collection) if collection else page_name.split()[0]
    # Capitalise nicely
    ent_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", ent_label).strip()

    # 5. Pick CRUD layout variant from entity's genome-assigned crud_layout
    crud_layout = "table"
    if entity:
        crud_layout = (entity.get("crud_layout") or "table").lower()
    # Map genome crud_layout → template variant
    _LAYOUT_MAP = {
        "table": "table", "table-dense": "table",
        "card-grid": "card-grid", "card_grid": "card-grid",
        "split-pane": "split-pane", "split_pane": "split-pane",
        "kanban": "table",    # kanban falls back to table for now
        "timeline": "table",  # timeline falls back to table for now
        "spreadsheet": "table",
    }
    layout = _LAYOUT_MAP.get(crud_layout, "table")

    return {
        "collection": collection,
        "display_fields": display_fields,
        "form_fields": form_fields,
        "create_label": f"New {ent_label}",
        "layout": layout,
    }


def _is_management_page(route: str, name: str) -> bool:
    """True for management / listing pages that should render as CRUD tables."""
    low_r = route.lower()
    low_n = name.lower()
    mgmt_kw = ("management", "manage", "listing", "list", "catalog", "registry",
                "directory", "roster", "records")
    return any(k in low_r or k in low_n for k in mgmt_kw)


# ── main entry point ──────────────────────────────────────────────────────────

_SKIP_ROUTES = {"/login", "/register", "/logout", "/dashboard"}


def write_srs_pages(out_dir: str, srs: dict, dm: dict) -> dict:
    """Generate protected page files from SRS application_pages.

    Returns:
        {"written": [rel_paths], "sidebar_extras": [{"label", "href", "roles"}]}
    """
    import json as _json

    written = []
    sidebar_extras = []
    reports = srs.get("reporting_requirements") or []
    notifications = srs.get("notification_requirements") or []
    app_pages = srs.get("app_pages") or []
    dom = _resolve_domain(dm)   # domain-resolved collections for POS/portal/inventory

    # collect entity collection names for report→collection mapping
    coll_map = {}
    for rep in reports:
        name = rep.get("name", "")
        slug = re.sub(r"[^a-z0-9]+", "", name.lower())
        # heuristic: "Sales Report" → possales, "Inventory Report" → inventorystocks, etc.
        for key, coll in _ROUTE_TO_COLLECTION.items():
            if key in slug or slug.startswith(key[:4]):
                coll_map[name] = coll
                break
        if name not in coll_map:
            coll_map[name] = "records"

    for page in app_pages:
        route = (page.get("route") or "").strip()
        if not route:
            continue
        # skip routes that are already handled by the scaffold/auth
        if route in _SKIP_ROUTES:
            continue
        if any(route.startswith(r) for r in ("/login", "/register")):
            continue

        name = page.get("name") or _label(route)
        roles = page.get("allowed_roles") or []
        functions = page.get("functions") or []
        roles_comment = ", ".join(roles[:4]) or "all"
        funcs_comment = "; ".join(functions[:3])
        funcs_json_str = _json.dumps(functions[:12])
        roles_js_str = _json.dumps(roles)

        # ── POS page ──
        if _is_pos_route(route):
            content = _POS_PAGE.format(
                page_name=name,
                page_name_jsx=name.replace("'", "\\'"),
                page_type_badge="POS",
                roles_comment=roles_comment,
                funcs_comment=funcs_comment[:100],
                catalog_collection=dom["catalog_collection"],
                catalog_label=dom["catalog_label"],
                catalog_label_lower=dom["catalog_label"].lower(),
                catalog_name_field=dom["catalog_name_field"],
                sale_collection=dom["sale_collection"],
            )

        # ── Report page ──
        elif _is_report_route(route):
            reports_json_str = _json.dumps([
                {"name": r.get("name", ""), "filters": r.get("filters", [])[:5]}
                for r in reports
            ])
            content = _REPORTS_PAGE.format(
                page_name=name,
                page_name_jsx=name.replace("'", "\\'"),
                roles_comment=roles_comment,
                reports_json=reports_json_str,
            )

        # ── Customer portal dashboard ──
        elif _is_customer_dash(route):
            sections = [
                {"label": "My " + dom["txn_label"] + "s"},
                {"label": "Completed"},
                {"label": "Pending"},
            ]
            content = _CUSTOMER_DASH.format(
                page_name=name,
                page_name_jsx=name.replace("'", "\\'"),
                sections_json=_json.dumps(sections),
                txn_collection=dom["txn_collection"],
                txn_label=dom["txn_label"],
                txn_label_lower=dom["txn_label"].lower(),
            )

        # ── Admin dashboard redirect handled by /dashboard scaffold ──
        elif _is_admin_dash(route):
            content = (
                "import { redirect } from 'next/navigation';\n"
                "export default function AdminDashboard() { redirect('/dashboard'); }\n"
            )

        # ── Prescription review page ──
        elif "prescription" in route.lower() and not route.endswith("/upload"):
            content = _PRESCRIPTION_REVIEW_PAGE.replace("{{", "{").replace("}}", "}")

        # ── Medicine management page ──
        elif "medicine" in route.lower() and "batch" not in route.lower():
            content = _MEDICINE_MGMT_PAGE.replace("{{", "{").replace("}}", "}")

        # ── Inventory / batch management page (only for domains that actually
        # have a batch+expiry entity, e.g. pharmacy; other domains fall through
        # to the generic admin section page below pointed at their stock entity) ──
        elif dom["has_batch"] and ("inventory" in route.lower() or "batch" in route.lower() or "stock" in route.lower()):
            content = (_INVENTORY_PAGE.replace("{{", "{").replace("}}", "}")
                       .replace("__BATCHCOLL__", dom["batch_collection"]))

        # ── CRUD management page (admin/* and any management/listing page) ──
        elif route.startswith("/admin/") or "/admin" in route or _is_management_page(route, name):
            ctx = _derive_crud_context(route, name, dm, functions)
            _fmt_args = dict(
                page_name=name,
                page_name_jsx=name.replace("'", "\\'"),
                roles_comment=roles_comment,
                collection=ctx["collection"],
                create_label=ctx["create_label"],
                display_fields_json=_json.dumps(ctx["display_fields"]),
                form_fields_json=_json.dumps(ctx["form_fields"]),
                funcs_json=funcs_json_str,
            )
            _tpl = {
                "card-grid": _CRUD_CARD_GRID_PAGE,
                "split-pane": _CRUD_SPLIT_PANE_PAGE,
            }.get(ctx.get("layout", "table"), _CRUD_MGMT_PAGE)
            content = _tpl.format(**_fmt_args)

        # ── Generic stub ──
        else:
            content = _STUB_PAGE.format(
                page_name=name,
                page_name_jsx=name.replace("'", "\\'"),
                roles_comment=roles_comment,
                funcs_json=funcs_json_str,
            )

        rel = _page_path(route)
        path = os.path.join(out_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(rel)

        # add to sidebar (skip auth + settings pages which are already in standard sidebar)
        skip_from_sidebar = {"/admin/settings", "/admin/dashboard", "/customer/dashboard"}
        if route not in skip_from_sidebar and roles:
            sidebar_extras.append({
                "label": _clean_nav_label(name),
                "href": route,
                "roles": roles,
                "icon": _route_icon(route),
            })

    # ── Reports API ──
    reports_api_content = _REPORTS_API.replace(
        "{coll_map}", _json.dumps(coll_map, indent=2)
    )
    _write(out_dir, "src/app/api/reports/route.js", reports_api_content, written)

    # ── Notification model ──
    events_json_str = _json.dumps([
        {"event": n.get("event", ""), "message": n.get("message", ""),
         "recipients": n.get("recipients", []), "channels": n.get("channels", [])}
        for n in notifications
    ])
    _write(out_dir, "src/lib/models/Notification.js",
           _NOTIF_MODEL.replace("{events_json}", events_json_str), written)
    _write(out_dir, "src/lib/services/NotificationService.js",
           _NOTIF_SERVICE.replace("{events_json}", events_json_str), written)
    _write(out_dir, "src/app/api/notifications/route.js", _NOTIF_API, written)

    return {"written": written, "sidebar_extras": sidebar_extras}


def _write(out_dir, rel, content, written_list):
    path = os.path.join(out_dir, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    written_list.append(rel)


_ICON_MAP = [
    ("pos", "ShoppingCart"), ("medicine", "Pill"), ("prescription", "FileText"),
    ("inventory", "Package"), ("supplier", "Truck"), ("purchase", "ClipboardList"),
    ("grn", "PackageCheck"), ("order", "ShoppingBag"), ("customer", "Users"),
    ("billing", "Receipt"), ("return", "RotateCcw"), ("staff", "UserCog"),
    ("report", "BarChart2"), ("setting", "Settings"), ("catalog", "BookOpen"),
    ("room", "Hotel"), ("vehicle", "Car"), ("student", "GraduationCap"),
    ("course", "BookOpen"), ("schedule", "CalendarDays"),
]


def _route_icon(route: str) -> str:
    low = route.lower()
    for key, icon in _ICON_MAP:
        if key in low:
            return icon
    return "Layers"
