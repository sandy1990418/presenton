import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);


/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  


  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "pub-7c765f3726084c52bcd5d180d51f1255.r2.dev",
      },
      {
        protocol: "https",
        hostname: "pptgen-public.ap-south-1.amazonaws.com",
      },
      {
        protocol: "https",
        hostname: "pptgen-public.s3.ap-south-1.amazonaws.com",
      },
      {
        protocol: "https",
        hostname: "img.icons8.com",
      },
      {
        protocol: "https",
        hostname: "present-for-me.s3.amazonaws.com",
      },
      {
        protocol: "https",
        hostname: "yefhrkuqbjcblofdcpnr.supabase.co",
      },
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "picsum.photos",
      },
      {
        protocol: "https",
        hostname: "unsplash.com",
      },
    ],
  },
  rewrites: async () => [
    {
      source: "/static/:path*",
      destination: "/api/static/:path*",
    },
    {
      source: "/app_data/:path*",
      destination: "/api/app_data/:path*",
    },
    {
      source: "/database/images/:path*",
      destination: "/app_data/images/:path*",
    },
    {
      source: "/database/exports/:path*",
      destination: "/app_data/exports/:path*",
    },
    {
      source: "/api/v1/ppt/:path*",
      destination: "http://localhost:8000/api/v1/ppt/:path*",
    },
    {
      source: "/.well-known/:path*",
      destination: "/api/not-found",
    },
  ],
};

export default nextConfig;
