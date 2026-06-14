'use client';
// Placeholder landing - REPLACED by the generator. Exercises the ui kit +
// lucide so the scaffold smoke-build proves the whole stack compiles.
import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { site } from '@/lib/site';

export default function Home() {
  return (
    <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-4 py-24 text-center">
      <Sparkles className="h-10 w-10 text-primary" />
      <h1 className="font-display text-4xl font-bold">{site.appName}</h1>
      <p className="text-muted-foreground">{site.tagline}</p>
      <Card className="w-full">
        <CardContent className="flex items-center justify-center gap-3 p-6">
          <Button onClick={() => (window.location.href = '/register')}>Get Started</Button>
          <Link href="/login" className="text-sm font-medium text-primary hover:underline">Sign in</Link>
        </CardContent>
      </Card>
    </section>
  );
}
