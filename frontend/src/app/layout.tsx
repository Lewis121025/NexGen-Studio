import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

import './globals.css';
import AppLayout from '@/components/layout/AppLayout';
import AuthGuard from '@/components/layout/AuthGuard';
import GlobalLoading from '@/components/layout/GlobalLoading';
import { Toaster } from '@/components/ui/sonner';

/**
 * Inter font configuration for Latin subset
 * Optimized for performance and readability
 */
const inter = Inter({ 
  subsets: ['latin'],
  display: 'swap',
  preload: true,
});

/**
 * Application metadata configuration
 * Defines SEO and social sharing properties
 */
export const metadata: Metadata = {
  title: {
    default: 'Lewis AI System',
    template: '%s | Lewis AI System',
  },
  description: 'Production-ready AI system with video creation, ReAct tasking, and enterprise-grade security',
  keywords: [
    'AI',
    'artificial intelligence',
    'video creation',
    'agentic coding',
    'task automation',
    'creative workflow',
    'ReAct framework',
  ],
  authors: [{ name: 'Lewis Engineering' }],
  creator: 'Lewis Engineering',
  metadataBase: new URL('https://lewis-ai.com'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://lewis-ai.com',
    siteName: 'Lewis AI System',
    title: 'Lewis AI System',
    description: 'Production-ready AI system with video creation and agentic tasking',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Lewis AI System',
    description: 'Production-ready AI system with video creation and agentic tasking',
  },
  robots: {
    index: false,
    follow: false,
  },
  manifest: '/manifest.json',
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
};

/**
 * Root layout component
 * 
 * This is the top-level layout that wraps all pages in the application.
 * It provides the global structure, authentication guards, and global UI components.
 * 
 * @param props.children - React components to render within the layout
 * @returns JSX.Element - The root layout structure
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): JSX.Element {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <AuthGuard>
          <AppLayout>{children}</AppLayout>
        </AuthGuard>
        <GlobalLoading />
        <Toaster 
          position="top-right" 
          closeButton
          toastOptions={{
            duration: 4000,
            style: {
              background: 'hsl(var(--background))',
              color: 'hsl(var(--foreground))',
              border: '1px solid hsl(var(--border))',
            },
          }}
        />
      </body>
    </html>
  );
}
