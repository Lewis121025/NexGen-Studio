'use client';

import { AlertCircle, RefreshCw } from 'lucide-react';
import { useEffect } from 'react';

import { Button } from '@/components/ui/button';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Application error:', error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0A0F]">
      <div className="text-center max-w-md px-6">
        <div className="flex justify-center mb-6">
          <div className="p-4 rounded-full bg-red-500/10">
            <AlertCircle className="w-12 h-12 text-red-500" />
          </div>
        </div>
        <h2 className="text-2xl font-bold text-white mb-4">出错了</h2>
        <p className="text-gray-400 mb-6">
          {error.message || '应用程序遇到了一个意外错误。'}
        </p>
        <Button
          onClick={reset}
          className="bg-primary hover:bg-primary/90"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          重试
        </Button>
      </div>
    </div>
  );
}
