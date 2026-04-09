'use client';

import dynamic from 'next/dynamic';

// Dynamically import to avoid SSR issues with socket.io / browser APIs
const SRSMakerPage = dynamic(() => import('../components/SRSMakerPage'), { ssr: false });

export default function Home() {
  return <SRSMakerPage />;
}
