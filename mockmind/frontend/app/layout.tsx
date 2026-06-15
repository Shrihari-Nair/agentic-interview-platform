import type { Metadata } from 'next';
import './globals.css';
import '@livekit/components-styles';

export const metadata: Metadata = {
  title: 'MockMind — AI Mock Interviews',
  description: 'AI-powered mock interviews personalized to your resume and target role.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
