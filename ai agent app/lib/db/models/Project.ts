import mongoose, { Schema, type InferSchemaType, type Model } from 'mongoose';

const FileSchema = new Schema(
  {
    path: { type: String, required: true },
    content: { type: String, default: '' },
  },
  { _id: false },
);

const ProjectSchema = new Schema(
  {
    // Human/URL friendly id (nanoid). We use a string _id so workspace folders
    // and DB documents share the same identifier.
    _id: { type: String, required: true },
    name: { type: String, required: true, default: 'Untitled app' },
    description: { type: String, default: '' },
    // Database name injected into the generated app's connection string.
    dbName: { type: String, default: '' },
    // Planning inputs + outputs (SRS-driven, type-aware planning).
    srs: { type: String, default: '' },
    appType: { type: String, default: '' },
    hasBackend: { type: Boolean, default: false },
    // Map of plan stage -> Markdown (master, pages, pagewise, components, backend, datatypes).
    plans: { type: Schema.Types.Mixed, default: {} },
    // Latest generated-app quality report (coverage, syntax, functional/design checks).
    audit: { type: Schema.Types.Mixed, default: null },
    // The latest full set of generated files.
    files: { type: [FileSchema], default: [] },
  },
  { timestamps: true },
);

export type ProjectFile = InferSchemaType<typeof FileSchema>;
export type ProjectDoc = InferSchemaType<typeof ProjectSchema>;

export const Project: Model<ProjectDoc> =
  (mongoose.models.Project as Model<ProjectDoc>) ||
  mongoose.model<ProjectDoc>('Project', ProjectSchema);
