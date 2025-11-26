/**
 * Studio Header - 顶部工具栏
 * 包含: 模式切换、会话标题、视图控制、系统操作
 */

'use client';

import { useStudioStore, selectCurrentSession } from '@/lib/stores/studio';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  MessageSquare,
  Video,
  Maximize2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function StudioHeader() {
  const mode = useStudioStore((state) => state.mode);
  const setMode = useStudioStore((state) => state.setMode);
  const layout = useStudioStore((state) => state.layout);
  const toggleSidebar = useStudioStore((state) => state.toggleSidebar);
  const toggleConfigPanel = useStudioStore((state) => state.toggleConfigPanel);
  const setCanvasViewMode = useStudioStore((state) => state.setCanvasViewMode);
  const currentSession = useStudioStore(selectCurrentSession);

  return (
    <header className="h-14 border-b border-border/50 bg-surface-2/80 backdrop-blur-sm flex items-center justify-between px-4">
      {/* 左侧: 侧边栏控制 + 模式切换 */}
      <div className="flex items-center gap-3">
        {/* 侧边栏切换 */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="text-muted-foreground hover:text-foreground"
        >
          {layout.sidebarOpen ? (
            <PanelLeftClose className="w-5 h-5" />
          ) : (
            <PanelLeftOpen className="w-5 h-5" />
          )}
        </Button>

        <Separator orientation="vertical" className="h-6" />

        {/* 模式切换标签 */}
        <div className="flex items-center gap-1 bg-surface-3/50 rounded-xl p-1">
          <Button
            variant={mode === 'general' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setMode('general')}
            className={cn(
              'rounded-lg gap-2 transition-all',
              mode === 'general'
                ? 'bg-primary-container text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <MessageSquare className="w-4 h-4" />
            <span className="font-medium">General</span>
          </Button>

          <Button
            variant={mode === 'creative' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setMode('creative')}
            className={cn(
              'rounded-lg gap-2 transition-all',
              mode === 'creative'
                ? 'bg-primary-container text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Video className="w-4 h-4" />
            <span className="font-medium">Creative</span>
          </Button>
        </div>
      </div>

      {/* 中间: 会话标题 */}
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="text-center max-w-md truncate">
          <h1 className="text-sm font-semibold text-foreground truncate">
            {currentSession?.title || 'Lewis AI Studio'}
          </h1>
          {currentSession && (
            <p className="text-xs text-muted-foreground">
              {mode === 'creative' ? '视频创作工作区' : 'AI 助手对话'}
            </p>
          )}
        </div>
      </div>

      {/* 右侧: 视图控制 + 配置面板 */}
      <div className="flex items-center gap-3">
        {/* 视图模式切换 */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() =>
            setCanvasViewMode(
              layout.canvasViewMode === 'focus' ? 'default' : 'focus'
            )
          }
          className="text-muted-foreground hover:text-foreground"
          title="专注模式"
        >
          <Maximize2 className="w-4 h-4" />
        </Button>

        <Separator orientation="vertical" className="h-6" />

        {/* 配置面板切换 */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleConfigPanel}
          className="text-muted-foreground hover:text-foreground"
          title="配置面板"
        >
          {layout.configPanelOpen ? (
            <PanelRightClose className="w-5 h-5" />
          ) : (
            <PanelRightOpen className="w-5 h-5" />
          )}
        </Button>
      </div>
    </header>
  );
}
