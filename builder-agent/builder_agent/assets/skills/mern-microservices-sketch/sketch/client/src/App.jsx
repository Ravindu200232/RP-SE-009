import { useEffect, useState } from 'react';
import { fetchProducts, formatPrice } from './api.js';

export function App() {
  const [products, setProducts] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetchProducts()
      .then((list) => { if (!cancelled) { setProducts(list); setStatus('ready'); } })
      .catch((cause) => { if (!cancelled) { setError(cause.message); setStatus('error'); } });
    return () => { cancelled = true; };
  }, []);

  if (status === 'loading') return <p role="status">Loading products…</p>;
  // A failed load is a visible state, not a blank page: a client that renders
  // nothing on error is indistinguishable from one that crashed.
  if (status === 'error') return <p role="alert">{error}</p>;

  return (
    <main>
      <h1>Products</h1>
      {products.length === 0 ? <p>No products yet.</p> : (
        <ul>
          {products.map((product) => (
            <li key={product.id}>
              <span>{product.name}</span>
              <span>{formatPrice(product.priceCents)}</span>
              <span>{product.stock > 0 ? 'In stock' : 'Sold out'}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
