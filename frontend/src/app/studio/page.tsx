/**
 * Studio Page - 主工作区入口
 * 使用完整的 StudioWorkspace 组件
 */

'use client';

import { Loader2, Sparkles } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useEffect, useState, useLayoutEffect } from 'react';

import { useStudioStore } from '@/lib/stores/studio';

// 使用 useLayoutEffect 在客户端，useEffect 在服务端
const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

function LoadingScreen() {
  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#0a0a0f]">
      <div className="text-center space-y-6">
        <div className="relative">
          <Sparkles className="w-16 h-16 text-blue-500 mx-auto animate-pulse" />
          <div className="absolute inset-0 w-16 h-16 border-2 border-blue-500/20 rounded-full mx-auto animate-ping" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold text-white">初始化工作区</h2>
          <p className="text-gray-400">正在加载 Lewis AI 系统...</p>
        </div>
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto" />
      </div>
    </div>
  );
}

// 动态导入 StudioWorkspace 避免 SSR 问题
const StudioWorkspace = dynamic(
  () => import('@/components/workspace/StudioWorkspace'),
  {
    ssr: false,
    loading: () => <LoadingScreen />,
  }
);

export default function StudioPage() {
  const [isHydrated, setIsHydrated] = useState(false);

  // 使用 useIsomorphicLayoutEffect 确保在首次渲染前完成 hydration
  useIsomorphicLayoutEffect(() => {
    // 恢复持久化的 store 状态
    useStudioStore.persist.rehydrate();
    setIsHydrated(true);
  }, []);

  // 在 hydration 完成前显示加载屏幕
  if (!isHydrated) {
    return <LoadingScreen />;
  }

  return <StudioWorkspace />;
}
