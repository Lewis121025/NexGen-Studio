"use client";

import { useUIStore } from "@/lib/stores/uiStore";

/**
 * 全局Loading遮罩层
 * 显示在整个应用上方，用于阻止用户交互
 */
export default function GlobalLoading() {
  const { isLoading, loadingMessage } = useUIStore();
  
  if (!isLoading) {
    return null;
  }
  
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="rounded-lg bg-[#0F0F14] border border-white/10 p-6 shadow-2xl">
        <div className="flex items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
          <div>
            <p className="text-white font-medium">{loadingMessage}</p>
            <p className="text-sm text-gray-400 mt-1">请稍候...</p>
          </div>
        </div>
      </div>
    </div>
  );
}
