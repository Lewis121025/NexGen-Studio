/**
 * Studio Shell - 三栏式布局容器
 * 采用 react-resizable-panels 实现可调整大小的工作区
 */

'use client';

import { GripVertical } from 'lucide-react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

import { useStudioStore } from '@/lib/stores/studio';

interface StudioShellProps {
  sidebar: React.ReactNode;
  canvas: React.ReactNode;
  configPanel: React.ReactNode;
}

export default function StudioShell({
  sidebar,
  canvas,
  configPanel,
}: StudioShellProps) {
  const layout = useStudioStore((state) => state.layout);
  const setSidebarWidth = useStudioStore((state) => state.setSidebarWidth);
  const setConfigPanelWidth = useStudioStore((state) => state.setConfigPanelWidth);

  return (
    <div className="h-screen w-screen overflow-hidden bg-surface-1">
      <PanelGroup direction="horizontal" className="h-full">
        {/* 左侧导航栏 */}
        {layout.sidebarOpen && (
          <>
            <Panel
              id="sidebar"
              defaultSize={20}
              minSize={15}
              maxSize={30}
              order={1}
              className="bg-surface-2"
              onResize={(size) => {
                // 根据百分比计算实际像素宽度
                if (typeof window !== 'undefined') {
                  const width = (window.innerWidth * size) / 100;
                  setSidebarWidth(width);
                }
              }}
            >
              {sidebar}
            </Panel>

            {/* 左侧分隔条 */}
            <PanelResizeHandle className="group relative w-1 bg-surface-3/50 hover:bg-primary/30 transition-colors">
              <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-1 group-hover:w-1.5 transition-all">
                <div className="flex items-center justify-center h-full">
                  <GripVertical className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            </PanelResizeHandle>
          </>
        )}

        {/* 中间画布区域 */}
        <Panel 
          id="canvas"
          defaultSize={60}
          minSize={40}
          order={2}
          className="bg-surface-1"
        >
          <div className="h-full flex flex-col">
            {canvas}
          </div>
        </Panel>

        {/* 右侧配置面板 */}
        {layout.configPanelOpen && (
          <>
            {/* 右侧分隔条 */}
            <PanelResizeHandle className="group relative w-1 bg-surface-3/50 hover:bg-primary/30 transition-colors">
              <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-1 group-hover:w-1.5 transition-all">
                <div className="flex items-center justify-center h-full">
                  <GripVertical className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            </PanelResizeHandle>

            <Panel
              id="config"
              defaultSize={20}
              minSize={18}
              maxSize={35}
              order={3}
              className="bg-surface-2 border-l border-border/50"
              onResize={(size) => {
                if (typeof window !== 'undefined') {
                  const width = (window.innerWidth * size) / 100;
                  setConfigPanelWidth(width);
                }
              }}
            >
              {configPanel}
            </Panel>
          </>
        )}
      </PanelGroup>
    </div>
  );
}
