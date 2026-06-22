// STUB model registry. Overwritten by mongoose_schema_generator.generate_models_index()
// once the data model planner runs - this empty default just keeps the bare
// scaffold (e.g. landing-page-only test builds) buildable on its own.
export const Models = {};

export const byCollection = {};

export function modelFor(collection) { return byCollection[collection] || null; }
