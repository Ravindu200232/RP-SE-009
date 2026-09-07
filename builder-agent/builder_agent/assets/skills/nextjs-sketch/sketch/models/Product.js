import mongoose from 'mongoose';

const productSchema = new mongoose.Schema({
  // `unique` is the index declaration. Adding schema.index({ slug: 1 }) as
  // well makes Mongoose warn about a duplicate index.
  slug: { type: String, required: true, unique: true, trim: true },
  name: { type: String, required: true, trim: true },
  priceCents: { type: Number, required: true, min: 0 },
  stock: { type: Number, required: true, min: 0, default: 0 },
}, { timestamps: true });

/** One serializer, so a server component and a route handler cannot disagree. */
productSchema.methods.toPublic = function toPublic() {
  return { id: String(this._id), slug: this.slug, name: this.name, priceCents: this.priceCents, stock: this.stock };
};

// A model compiled twice — by a test file and by the app, or by a hot reload —
// throws OverwriteModelError.
export const Product = mongoose.models.Product ?? mongoose.model('Product', productSchema);
