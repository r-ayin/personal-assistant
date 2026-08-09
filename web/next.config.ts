import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  distDir: "dist",
  basePath: "/web",
  assetPrefix: "/web",
  trailingSlash: true,
};

export default nextConfig;
