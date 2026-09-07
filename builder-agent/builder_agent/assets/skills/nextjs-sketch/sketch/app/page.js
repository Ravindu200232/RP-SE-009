import { listProducts } from '@/lib/products.js';
import { ProductList } from '@/components/ProductList.jsx';

// This page reads the database on every request. Without it Next.js would
// serve a build-time snapshot and new products would never appear.
export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const products = await listProducts();
  return (
    <main>
      <h1>Products</h1>
      <ProductList products={products} />
    </main>
  );
}
