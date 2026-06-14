'use client';
// Generic DETAIL page for every entity.
import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Pencil } from 'lucide-react';
import { api } from '@/lib/api';
import { entityBySlug, fieldLabel, statusVariant } from '@/lib/entities';
import { Button } from '@/components/ui/button';
import { Badge, Separator } from '@/components/ui/extras';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

export default function EntityDetail() {
  const { entity: slug, id } = useParams();
  const router = useRouter();
  const entity = entityBySlug(slug);
  const [rec, setRec] = React.useState(undefined);

  React.useEffect(() => {
    if (!entity || !id) return;
    api.get(entity.name, id).then(setRec).catch(() => setRec(null));
  }, [entity && entity.name, id]);

  if (!entity) return <div className="p-10 text-center text-muted-foreground">Unknown section.</div>;
  if (rec === undefined) return <div className="p-10 text-center text-muted-foreground">Loading...</div>;
  if (rec === null) {
    return (
      <div className="p-10 text-center">
        <p className="mb-4 text-muted-foreground">Record not found.</p>
        <Button variant="outline" onClick={() => router.push(`/e/${slug}`)}><ArrowLeft /> Back to {entity.label}</Button>
      </div>
    );
  }

  const fields = (entity.fields || []).filter((f) => f.name !== 'id');
  const title = String(rec[fields[0]?.name] ?? entity.label);

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle className="font-display text-2xl">{title}</CardTitle>
            <CardDescription>{entity.label} details</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => router.push(`/e/${slug}/${id}/edit`)}><Pencil /> Edit</Button>
            <Button variant="outline" onClick={() => router.push(`/e/${slug}`)}><ArrowLeft /> Back</Button>
          </div>
        </CardHeader>
        <CardContent>
          <Separator className="mb-5" />
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {fields.map((f) => (
              <div key={f.name}>
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{fieldLabel(f)}</dt>
                <dd className="mt-1 text-sm">
                  {f.name === 'status'
                    ? <Badge variant={statusVariant(rec[f.name])}>{String(rec[f.name] ?? '-')}</Badge>
                    : String(rec[f.name] ?? '-')}
                </dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
