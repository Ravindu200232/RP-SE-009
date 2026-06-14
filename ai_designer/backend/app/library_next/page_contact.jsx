'use client';
import * as React from 'react';
import { useState } from 'react';
import { Icon } from '@/components/ui/icon';

export default function Contact() {
  const hide = (e) => { e.currentTarget.style.display = 'none'; };
  const [form, setForm] = useState({ name: '', email: '', subject: '', department: '', message: '' });
  const [errors, setErrors] = useState({});
  const [sent, setSent] = useState(false);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const submit = (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.name.trim()) errs.name = 'Required';
    if (!form.email.trim()) errs.email = 'Required';
    if (!form.message.trim()) errs.message = 'Required';
    setErrors(errs);
    if (Object.keys(errs).length === 0) setSent(true);
  };

  const details = [
    { icon: 'map-pin', label: 'Address', value: '123 Main Street, City, Country' },
    { icon: 'phone', label: 'Phone', value: '+1 (555) 010-2030' },
    { icon: 'mail', label: 'Support email', value: 'support@example.com' },
    { icon: 'clock', label: 'Hours', value: 'Mon-Fri, 9:00 - 18:00' },
  ];

  const input = 'flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring';

  return (
    <div className="w-full">
      <section className="px-4 pb-12 pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-primary">Contact</p>
          <h1 className="font-display text-4xl font-bold tracking-tight md:text-6xl">We'd love to hear from you</h1>
          <p className="mt-5 text-lg text-muted-foreground">Questions, feedback or a demo request - send a message and we'll reply within one business day.</p>
        </div>
      </section>

      <section className="px-4 pb-24">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-2">
          {/* form */}
          <div className="rounded-2xl border bg-card p-7 shadow-sm">
            <h2 className="mb-5 font-display text-xl font-bold">Send a message</h2>
            {sent ? (
              <div className="flex flex-col items-center gap-3 rounded-xl bg-primary/5 p-10 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 text-primary"><Icon name="check" className="h-6 w-6" /></span>
                <p className="font-semibold">Thanks - we'll be in touch!</p>
                <p className="text-sm text-muted-foreground">Your message has been received.</p>
              </div>
            ) : (
              <form onSubmit={submit} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">Name</label>
                    <input className={input} value={form.name} onChange={(e) => set('name', e.target.value)} />
                    {errors.name && <p className="mt-1 text-xs text-destructive">{errors.name}</p>}
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">Email</label>
                    <input type="email" className={input} value={form.email} onChange={(e) => set('email', e.target.value)} />
                    {errors.email && <p className="mt-1 text-xs text-destructive">{errors.email}</p>}
                  </div>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">Subject</label>
                  <input className={input} value={form.subject} onChange={(e) => set('subject', e.target.value)} />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">Department</label>
                  <select className={input} value={form.department} onChange={(e) => set('department', e.target.value)}>
                    <option value="">Select...</option>
                    <option>Sales</option>
                    <option>Support</option>
                    <option>Partnerships</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">Message</label>
                  <textarea rows={5} className={input + ' h-auto'} value={form.message} onChange={(e) => set('message', e.target.value)} />
                  {errors.message && <p className="mt-1 text-xs text-destructive">{errors.message}</p>}
                </div>
                <button type="submit" className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-6 text-sm font-semibold text-primary-foreground shadow transition hover:bg-primary/90">
                  Send message
                </button>
              </form>
            )}
          </div>

          {/* details + photo */}
          <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              {details.map((d) => (
                <div key={d.label} className="rounded-2xl border bg-card p-5 shadow-sm">
                  <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon name={d.icon} className="h-4 w-4" /></span>
                  <p className="text-sm font-semibold">{d.label}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">{d.value}</p>
                </div>
              ))}
            </div>
            <img src="/assets/contact.jpg" alt="" onError={hide} className="h-64 w-full rounded-2xl object-cover shadow-md" />
          </div>
        </div>
      </section>
    </div>
  );
}
