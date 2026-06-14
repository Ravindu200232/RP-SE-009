'use client';
// Deterministic settings page - working toggles + save toast.
import * as React from 'react';
import { Check } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Switch, Input, Label } from '@/components/ui/form';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/extras';
import { site } from '@/lib/site';

const TOGGLES = [
  ['Email notifications', 'Receive a summary of important activity by email.'],
  ['Push notifications', 'Get notified in the browser when something needs you.'],
  ['Weekly report', 'A digest of the week, every Monday morning.'],
  ['Dark sidebar', 'Use the darker sidebar styling.'],
];

export default function SettingsPage() {
  const [flags, setFlags] = React.useState({ 0: true, 1: false, 2: true, 3: false });
  const [name, setName] = React.useState(site.appName);
  const [saved, setSaved] = React.useState(false);

  const save = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6 md:p-8">
      <h1 className="font-display text-2xl font-bold md:text-3xl">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">General</CardTitle>
          <CardDescription>Workspace basics.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="ws">Workspace name</Label>
            <Input id="ws" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Notifications</CardTitle>
          <CardDescription>Choose what you want to hear about.</CardDescription>
        </CardHeader>
        <CardContent>
          {TOGGLES.map(([title, desc], i) => (
            <div key={title}>
              <div className="flex items-center justify-between py-3">
                <div className="pr-6">
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
                <Switch checked={!!flags[i]} onCheckedChange={(v) => setFlags((p) => ({ ...p, [i]: v }))} />
              </div>
              {i < TOGGLES.length - 1 && <Separator />}
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save}>Save changes</Button>
        {saved && <span className="flex items-center gap-1.5 text-sm font-medium text-emerald-600"><Check className="h-4 w-4" /> Saved</span>}
      </div>
    </div>
  );
}
