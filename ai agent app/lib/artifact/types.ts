export interface GeneratedFile {
  path: string;
  content: string;
}

export interface ParsedArtifact {
  name?: string;
  description?: string;
  files: GeneratedFile[];
}
