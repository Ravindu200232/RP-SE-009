import Link from 'next/link';
import { notFound } from 'next/navigation';
import { findProduct } from '@/lib/products.js';
import { formatPrice } from '@/lib/money.js';

export const dynamic = 'force-dynamic';

// In Next 15 `params` is a Promise. Reading `params.slug` directly gives
// undefined, and the page 404s for every request with no error to explain it.
export default async function ProductPage({ params }) {
  const { slug } = await params;
  const product = await findProduct(slug);
  if (!product) notFound();

  return (
    <main>
      {/* Link, not <a>: a plain anchor forces a full document reload and loses
          client state. */}
      <Link href="/">Back to products</Link>
      <h1>{product.name}</h1>
      <p>{formatPrice(product.priceCents)}</p>
      <p>{product.stock > 0 ? 'In stock' : 'Sold out'}</p>
    </main>
  );
}
