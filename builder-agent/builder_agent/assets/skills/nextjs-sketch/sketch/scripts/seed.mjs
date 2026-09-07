import mongoose from 'mongoose';
import { Product } from '../models/Product.js';

/**
 * The seed imports the application's own model.
 *
 * A script that declares its own schema writes to a collection named after
 * that model — `seedproducts` instead of `products` — and then reports success
 * while the application serves nothing.
 */
const uri = process.env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017/sketch_next';
await mongoose.connect(uri);

// The seed owns this collection, so it clears it. Documents from an earlier
// version of the app survive with a different field shape and get rendered.
await Product.deleteMany({});
await Product.create([
  { slug: 'desk-lamp', name: 'Desk lamp', priceCents: 4500, stock: 12 },
  { slug: 'oak-chair', name: 'Oak chair', priceCents: 12000, stock: 4 },
  { slug: 'notebook', name: 'Notebook', priceCents: 850, stock: 0 },
]);

console.log('seeded ' + (await Product.countDocuments()) + ' products');
await mongoose.disconnect();
