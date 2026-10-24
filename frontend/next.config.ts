import type { NextConfig } from 'next';
import { fileURLToPath } from 'node:url';
const nextConfig: NextConfig = {
  poweredByHeader: false,
  turbopack: { root: fileURLToPath(new URL('.', import.meta.url)) },
  logging: false,
  agentRules: false,
  devIndicators: false,
};
export default nextConfig;
