'use client';
// Generic CREATE page for every entity (form from field metadata).
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { entityBySlug } from '@/lib/entities';
import EntityForm from '@/components/shell/EntityForm';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

export default function EntityCreate() {
  const { entity: slug } = useParams();
  const router = useRouter();
  const entity = entityBySlug(slug);
  if (!entity) return <div className="p-10 text-center text-muted-foreground">Unknown section.</div>;

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-2xl">Add {entity.label}</CardTitle>
          <CardDescription>Fill in the details below and save.</CardDescription>
        </CardHeader>
        <CardContent>
          <EntityForm
            entity={entity}
            submitLabel={`Create ${entity.label}`}
            onSubmit={async (form) => {
              await api.create(entity.name, form);
              router.push(`/e/${slug}`);
            }}
            onCancel={() => router.push(`/e/${slug}`)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
