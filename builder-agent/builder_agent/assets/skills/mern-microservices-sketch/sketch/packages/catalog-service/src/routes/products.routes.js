import { Router } from 'express';
import { Product } from '../models/product.js';

export const productsRouter = Router();

productsRouter.get('/', async (req, res, next) => {
  try {
    const filter = {};
    if (req.query.q) filter.name = { $regex: String(req.query.q), $options: 'i' };
    const products = await Product.find(filter).sort({ name: 1 }).limit(100);
    res.json({ products: products.map((product) => product.toPublic()) });
  } catch (error) { next(error); }
});

productsRouter.get('/:slug', async (req, res, next) => {
  try {
    const product = await Product.findOne({ slug: req.params.slug });
    if (!product) return res.status(404).json({ error: 'Product not found' });
    res.json({ product: product.toPublic() });
  } catch (error) { next(error); }
});

productsRouter.post('/:slug/reserve', async (req, res, next) => {
  try {
    const quantity = Number(req.body?.quantity ?? 1);
    if (!Number.isInteger(quantity) || quantity < 1) {
      return res.status(400).json({ error: 'quantity must be a positive integer' });
    }
    // The guard lives in the query, so two callers cannot both pass a
    // read-then-write check and drive stock below zero.
    const product = await Product.findOneAndUpdate(
      { slug: req.params.slug, stock: { $gte: quantity } },
      { $inc: { stock: -quantity } },
      { new: true },
    );
    if (!product) return res.status(409).json({ error: 'Insufficient stock' });
    res.json({ product: product.toPublic() });
  } catch (error) { next(error); }
});
