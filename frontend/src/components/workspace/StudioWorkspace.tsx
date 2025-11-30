/**
 * Studio Workspace - 主工作区容器
 * 完全客户端渲染,处理所有 Zustand store 交互
 */

'use client';

import { Loader2 } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useEffect, Suspense } from 'react';

import ConfigPanel from '@/components/layout/ConfigPanel';
import StudioHeader from '@/components/layout/StudioHeader';
import StudioShell from '@/components/layout/StudioShell';
import StudioSidebar from '@/components/layout/StudioSidebar';
import { useStudioStore } from '@/lib/stores/studio';


// 画布加载器
function CanvasLoader() {
  return (
    <div className="h-full flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-primary animate-spin" />
    </div>
  );
}

// 动态导入画布组件
const GeneralCanvas = dynamic(
  () => import('@/components/workspace/GeneralCanvas'),
  { 
    ssr: false,
    loading: CanvasLoader
  }
);

const CreativeCanvas = dynamic(
  () => import('@/components/workspace/CreativeCanvas'),
  { 
    ssr: false,
    loading: CanvasLoader
  }
);

export default function StudioWorkspace() {
  const mode = useStudioStore((state) => state.mode);
  
  // 初始化逻辑 - 只执行一次,使用 ref 跟踪
  useEffect(() => {
    const store = useStudioStore.getState();
    
    // 只在首次加载且没有会话时创建
    if (!store.currentSessionId && store.sessions.length === 0) {
      store.createSession(store.mode);
    }
  }, []); // 空依赖数组,只执行一次

  // 选择要渲染的画布
  const Canvas = mode === 'general' ? GeneralCanvas : CreativeCanvas;

  return (
    <StudioShell
      sidebar={<StudioSidebar />}
      canvas={
        <div className="h-full flex flex-col">
          <StudioHeader />
          <div className="flex-1 overflow-hidden">
            <Suspense fallback={<CanvasLoader />}>
              <Canvas />
            </Suspense>
          </div>
        </div>
      }
      configPanel={<ConfigPanel />}
    />
  );
}
