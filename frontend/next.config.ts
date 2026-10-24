import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The floating dev badge covers the sidebar's model status; errors still show in the overlay.
  devIndicators: false,
  // The desktop app ships the frontend as pre-built static files served by the backend
  // (MECH_STATIC_EXPORT=1, see desktop/build.ps1). Normal `next build` / `next start` is unchanged.
  ...(process.env.MECH_STATIC_EXPORT === "1"
    ? { output: "export" as const, trailingSlash: true, env: { NEXT_PUBLIC_SAME_ORIGIN: "1" } }
    : {}),
};

export default nextConfig;
