/**
 * Home Page Component
 * 
 * This is the landing page that automatically redirects users to the main studio workspace.
 * It provides a loading state while the redirect is processed.
 *
 * @returns JSX.Element - The loading screen with automatic redirect
 */

'use client';

import { Loader2, Sparkles } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

/**
 * Home page component with automatic redirect
 */
export default function Home(): JSX.Element {
  const router = useRouter();

  useEffect(() => {
    // 立即重定向到studio页面，避免加载循环
    router.replace('/studio');
  }, [router]);

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20">
      <div className="text-center space-y-8 max-w-md mx-auto px-4">
        {/* Logo and Brand */}
        <div className="space-y-4">
          <div className="relative">
            <Sparkles className="w-16 h-16 text-primary mx-auto animate-pulse" />
            <div className="absolute inset-0 w-16 h-16 border-2 border-primary/20 rounded-full mx-auto animate-ping" />
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
              Lewis AI System
            </h1>
            <p className="text-sm text-muted-foreground">
              Production-Ready AI Platform
            </p>
          </div>
        </div>

        {/* Loading State */}
        <div className="space-y-6">
          <Loader2 className="w-8 h-8 text-primary animate-spin mx-auto" />
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-foreground">
              Initializing Workspace
            </h2>
            <p className="text-sm text-muted-foreground">
              Preparing your AI development environment...
            </p>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex justify-center space-x-1">
          <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  );
}
