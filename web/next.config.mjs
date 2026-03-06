/** @type {import('next').NextConfig} */
const nextConfig = {
    // Disable server-only features for static export
    images: {
        unoptimized: true,
    },
    eslint: {
        ignoreDuringBuilds: true,
    },
    typescript: {
        ignoreBuildErrors: true,
    }
};

export default nextConfig;
