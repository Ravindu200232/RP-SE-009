'use client';

import Link from 'next/link';
import { formatPrice } from '@/lib/money.js';

/**
 * A client component because it will hold interaction later. Everything it
 * needs arrives as props, so the server component above it stays the only
 * thing that touches the database.
 */
export function ProductList({ products }) {
  // An empty result is a state with words in it. A component that renders
  // nothing is indistinguishable from one that crashed.
  if (!products?.length) return <p>No products yet.</p>;

  return (
    <ul>
      {products.map((product) => (
        <li key={product.id}>
          <Link href={`/products/${product.slug}`}>{product.name}</Link>
          <span>{formatPrice(product.priceCents)}</span>
          <span>{product.stock > 0 ? 'In stock' : 'Sold out'}</span>
        </li>
      ))}
    </ul>
  );
}
