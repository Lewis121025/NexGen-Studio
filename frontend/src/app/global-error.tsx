'use client';

import { AlertCircle, RefreshCw, Home } from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body className="bg-[#0A0A0F]">
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center max-w-md px-6">
            <div className="flex justify-center mb-6">
              <div className="p-4 rounded-full bg-red-500/10">
                <AlertCircle className="w-12 h-12 text-red-500" />
              </div>
            </div>
            <h2 className="text-2xl font-bold text-white mb-4">应用错误</h2>
            <p className="text-gray-400 mb-6">
              {error.message || '应用程序遇到了一个严重错误。'}
            </p>
            <div className="flex gap-4 justify-center">
              <Button
                onClick={reset}
                className="bg-primary hover:bg-primary/90"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                重试
              </Button>
              <Button asChild variant="outline">
                <Link href="/">
                  <Home className="w-4 h-4 mr-2" />
                  返回首页
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
