'use client';
// Shared create/edit form rendered from entity field metadata. Every value is
// kept as a string in state (controlled inputs can never flip uncontrolled).
import * as React from 'react';
import { Input, Textarea, Label, Select, Checkbox } from '@/components/ui/form';
import { Button } from '@/components/ui/button';

export default function EntityForm({ entity, initial = {}, onSubmit, onCancel, submitLabel = 'Save' }) {
  const fields = (entity?.fields || []).filter((f) => f.name !== 'id');
  const init = {};
  for (const f of fields) init[f.name] = initial[f.name] != null ? String(initial[f.name]) : '';
  const [form, setForm] = React.useState(init);
  const [errors, setErrors] = React.useState({});
  const [busy, setBusy] = React.useState(false);

  const set = (name, value) => setForm((p) => ({ ...p, [name]: value }));

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    for (const f of fields) {
      if (f.required !== false && !String(form[f.name] ?? '').trim() && f.type !== 'checkbox') {
        errs[f.name] = 'Required';
      }
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await onSubmit(form);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        {fields.map((f) => (
          <div key={f.name} className={f.type === 'textarea' ? 'sm:col-span-2 space-y-1.5' : 'space-y-1.5'}>
            <Label htmlFor={f.name}>{f.label || f.name}</Label>
            {f.type === 'textarea' ? (
              <Textarea id={f.name} rows={4} value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} />
            ) : f.type === 'select' ? (
              <Select id={f.name} value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)}>
                <option value="">Select...</option>
                {(f.options || []).map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </Select>
            ) : f.type === 'checkbox' ? (
              <div className="flex h-9 items-center"><Checkbox id={f.name} checked={form[f.name] === 'true'} onChange={(e) => set(f.name, e.target.checked ? 'true' : 'false')} /></div>
            ) : (
              <Input id={f.name} type={f.type || 'text'} value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} />
            )}
            {errors[f.name] && <p className="text-xs text-destructive">{errors[f.name]}</p>}
          </div>
        ))}
      </div>
      <div className="flex gap-3">
        <Button type="submit" disabled={busy}>{busy ? 'Saving...' : submitLabel}</Button>
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
