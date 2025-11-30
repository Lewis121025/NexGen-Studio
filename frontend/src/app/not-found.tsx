import { Home, Search } from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0A0F]">
      <div className="text-center max-w-md px-6">
        <div className="text-8xl font-bold text-gray-700 mb-4">404</div>
        <h2 className="text-2xl font-bold text-white mb-4">页面未找到</h2>
        <p className="text-gray-400 mb-6">
          您访问的页面不存在或已被移除。
        </p>
        <div className="flex gap-4 justify-center">
          <Button asChild className="bg-primary hover:bg-primary/90">
            <Link href="/">
              <Home className="w-4 h-4 mr-2" />
              返回首页
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/studio">
              <Search className="w-4 h-4 mr-2" />
              进入工作室
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
