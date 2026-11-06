/** Generated from contracts — keep in sync with JSON Schema / OpenAPI. */
export type CanonicalChunk = {
  schema_version: "1.0.0";
  chunk_id: string;
  chunk_run_id: string;
  document_id: string;
  document_version_id: string;
  tenant_id: string;
  text: string;
  embedding_text?: string | null;
  extensions?: { provider_payload?: Record<string, unknown> };
};
