import path from "path";
import type { NextConfig } from "next";

const staticExport = process.env.NEXT_PUBLIC_STATIC_EXPORT === "true";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: staticExport ? "export" : undefined,
  images: {
    unoptimized: staticExport,
  },
  outputFileTracingRoot: path.join(__dirname, ".."),
};

export default nextConfig;
