/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Browser calls same-origin `/api/v1/*` via `src/app/api/v1/[...path]/route.ts`
  // which proxies to API_INTERNAL_URL at runtime (works in Compose + public tunnels).
};
export default nextConfig;
