import mongoose from 'mongoose';

const productSchema = new mongoose.Schema({
  // `unique` declares the index here; declaring it again with schema.index()
  // makes Mongoose warn about a duplicate index.
  slug: { type: String, required: true, unique: true, trim: true },
  name: { type: String, required: true, trim: true },
  priceCents: { type: Number, required: true, min: 0 },
  stock: { type: Number, required: true, min: 0, default: 0 },
}, { timestamps: true });

/** The API shape is decided here, once, so every route serializes identically. */
productSchema.methods.toPublic = function toPublic() {
  return { id: String(this._id), slug: this.slug, name: this.name, priceCents: this.priceCents, stock: this.stock };
};

// Compiling the same model twice throws OverwriteModelError when a test file
// and the application both import this module.
export const Product = mongoose.models.Product ?? mongoose.model('Product', productSchema);
