'use client';
// Generic EDIT page for every entity (prefilled form from field metadata).
import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { entityBySlug } from '@/lib/entities';
import EntityForm from '@/components/shell/EntityForm';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function EntityEdit() {
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
        <Button variant="outline" onClick={() => router.push(`/e/${slug}`)}>Back to {entity.label}</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-2xl">Edit {entity.label}</CardTitle>
          <CardDescription>Update the details below and save.</CardDescription>
        </CardHeader>
        <CardContent>
          <EntityForm
            entity={entity}
            initial={rec}
            submitLabel="Save changes"
            onSubmit={async (form) => {
              await api.update(entity.name, id, form);
              router.push(`/e/${slug}/${id}`);
            }}
            onCancel={() => router.push(`/e/${slug}/${id}`)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
