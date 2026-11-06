/** Lightweight API client mirroring OpenAPI /api/v1. */
export async function apiGet<T>(baseUrl: string, path: string, headers: Record<string, string> = {}): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, { headers: { "X-Tenant-Id": "tenant_dev", ...headers } });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}
