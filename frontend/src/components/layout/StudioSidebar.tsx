/**
 * Studio Sidebar - 左侧导航与资产管理
 * 功能: 会话切换、历史记录、资产库(Creative模式)
 */

'use client';

import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import {
  Plus,
  MessageSquare,
  Video,
  Image as ImageIcon,
  FileText,
  Clock,
  Trash2,
} from 'lucide-react';
import Image from 'next/image';
import { useMemo, useState } from 'react';
import type { JSX } from 'react';

import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useStudioStore } from '@/lib/stores/studio';
import type { AssetLibraryItem, Session } from '@/lib/stores/types';
import { cn } from '@/lib/utils';

export default function StudioSidebar(): JSX.Element {
  const mode = useStudioStore((state) => state.mode);
  const currentSessionId = useStudioStore((state) => state.currentSessionId);
  const createSession = useStudioStore((state) => state.createSession);
  const switchSession = useStudioStore((state) => state.switchSession);
  const deleteSession = useStudioStore((state) => state.deleteSession);
  const sessions = useStudioStore((state) => state.sessions);
  const assets = useStudioStore((state) => state.assets);

  const [activeTab, setActiveTab] = useState<'sessions' | 'assets'>('sessions');

  // ʹ�� useMemo ����ɸѡ���,����������Ⱦ
  const filteredSessions = useMemo(
    () => sessions.filter((s) => s.mode === mode),
    [sessions, mode],
  );

  const handleNewSession = (): void => {
    const session = createSession(mode);
    // 自动切换到新会话
    switchSession(session.id);
  };

  return (
    <div className="h-full flex flex-col bg-surface-2">
      {/* 顶部: 新建按钮 */}
      <div className="p-4 space-y-3">
        <Button
          onClick={handleNewSession}
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium rounded-google shadow-sm transition-smooth hover-lift"
        >
          <Plus className="w-4 h-4 mr-2" />
          {mode === 'general' ? '新对话' : '新项目'}
        </Button>

        {/* Tab 切换 */}
        <div className="flex gap-1 bg-surface-3/50 rounded-google p-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActiveTab('sessions')}
            className={cn(
              'flex-1 rounded-lg text-xs',
              activeTab === 'sessions'
                ? 'bg-surface-1 text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Clock className="w-3 h-3 mr-1" />
            历史
          </Button>
          {mode === 'creative' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setActiveTab('assets')}
              className={cn(
                'flex-1 rounded-lg text-xs',
                activeTab === 'assets'
                  ? 'bg-surface-1 text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <ImageIcon className="w-3 h-3 mr-1" />
              资产
            </Button>
          )}
        </div>
      </div>

      <Separator className="bg-border/50" />

      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto px-2 scrollbar-thin scrollbar-thumb-surface-3 scrollbar-track-transparent">
        {activeTab === 'sessions' ? (
          <SessionList
            sessions={filteredSessions}
            currentSessionId={currentSessionId}
            onSelect={switchSession}
            onDelete={deleteSession}
          />
        ) : (
          <AssetLibrary assets={assets} />
        )}
      </div>

      {/* 底部信息 */}
      <div className="p-4 border-t border-border/30">
        <div className="text-xs text-muted-foreground text-center">
          <p className="font-medium">Lewis AI Studio</p>
          <p className="text-[10px] mt-1">
            {filteredSessions.length} {mode === 'general' ? '个对话' : '个项目'}
          </p>
        </div>
      </div>
    </div>
  );
}

// ==================== 会话列表 ====================
interface SessionListProps {
  sessions: Session[];
  currentSessionId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

function SessionList({
  sessions,
  currentSessionId,
  onSelect,
  onDelete,
}: SessionListProps): JSX.Element {
  return (
    <div className="space-y-1 py-2">
      {sessions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <MessageSquare className="w-12 h-12 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">暂无历史记录</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            点击上方按钮开始新会话
          </p>
        </div>
      ) : (
        sessions.map((session) => (
          <div
            key={session.id}
            className={cn(
              'group relative rounded-google p-3 cursor-pointer transition-all',
              currentSessionId === session.id
                ? 'bg-primary-container/20 border border-primary/30'
                : 'hover:bg-surface-3/50'
            )}
            onClick={() => onSelect(session.id)}
          >
            <div className="flex items-start gap-3">
              {/* 图标 */}
              <div
                className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                  currentSessionId === session.id
                    ? 'bg-primary/20'
                    : 'bg-surface-3'
                )}
              >
                {session.mode === 'creative' ? (
                  <Video className="w-4 h-4 text-primary" />
                ) : (
                  <MessageSquare className="w-4 h-4 text-primary" />
                )}
              </div>

              {/* 内容 */}
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-foreground truncate">
                  {session.title}
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatDistanceToNow(new Date(session.updatedAt), {
                    addSuffix: true,
                    locale: zhCN,
                  })}
                </p>
              </div>

              {/* 删除按钮 */}
              <Button
                variant="ghost"
                size="icon"
                className="opacity-0 group-hover:opacity-100 transition-opacity w-7 h-7"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(session.id);
                }}
              >
                <Trash2 className="w-3 h-3 text-destructive" />
              </Button>
            </div>

            {/* 消息预览 (如果有) */}
            {session.messages && session.messages.length > 0 && (
              <p className="text-xs text-muted-foreground/80 mt-2 truncate">
                {session.messages[session.messages.length - 1].content}
              </p>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ==================== 资产库 ====================
interface AssetLibraryProps {
  assets: AssetLibraryItem[];
}

function AssetLibrary({ assets }: AssetLibraryProps): JSX.Element {
  // 安全检查
  
  return (
    <div className="space-y-2 py-2">
      {assets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <ImageIcon className="w-12 h-12 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">暂无资产</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            生成的视频和图片会显示在这里
          </p>
        </div>
      ) : (
        assets.map((asset) => (
          <div
            key={asset.id}
            className="group rounded-google overflow-hidden bg-surface-3/30 hover:bg-surface-3 transition-all cursor-pointer"
          >
            {/* 缩略图 */}
            {asset.thumbnailUrl && (
              <div className="aspect-video bg-surface-3 relative overflow-hidden">
                <Image
                  src={asset.thumbnailUrl}
                  alt={asset.title}
                  className="object-cover"
                  fill
                  sizes="100vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            )}

            {/* 信息 */}
            <div className="p-3">
              <div className="flex items-start gap-2">
                <div
                  className={cn(
                    'w-6 h-6 rounded flex items-center justify-center flex-shrink-0',
                    'bg-surface-1'
                  )}
                >
                  {asset.type === 'video' && (
                    <Video className="w-3 h-3 text-primary" />
                  )}
                  {asset.type === 'image' && (
                    <ImageIcon className="w-3 h-3 text-primary" />
                  )}
                  {asset.type === 'script' && (
                    <FileText className="w-3 h-3 text-primary" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-foreground truncate">
                    {asset.title}
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {formatDistanceToNow(new Date(asset.createdAt), {
                      addSuffix: true,
                      locale: zhCN,
                    })}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}