import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // @ts-expect-error - Next.js error suggests this property but types might not have it yet
  allowedDevOrigins: ['192.168.4.105'],
};

export default nextConfig;
