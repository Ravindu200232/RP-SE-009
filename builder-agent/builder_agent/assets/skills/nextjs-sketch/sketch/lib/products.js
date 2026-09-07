import { connectDb } from '@/lib/db.js';
import { Product } from '@/models/Product.js';

/**
 * Data access the pages share.
 *
 * Server components call this directly — going through the app's own HTTP API
 * from a server component costs a network round trip to itself.
 */
export async function listProducts(query = '') {
  await connectDb();
  const filter = query ? { name: { $regex: String(query), $options: 'i' } } : {};
  const products = await Product.find(filter).sort({ name: 1 }).limit(100);
  return products.map((product) => product.toPublic());
}

export async function findProduct(slug) {
  await connectDb();
  const product = await Product.findOne({ slug });
  return product ? product.toPublic() : null;
}
