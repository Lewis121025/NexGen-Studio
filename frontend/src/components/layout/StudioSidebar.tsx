/**
 * Studio Sidebar - 左侧导航与资产管理
 * 功能: 会话切换、历史记录、资产库(Creative模式)
 */

'use client';

import { useState, useMemo, useEffect } from 'react';
import { useStudioStore, selectSessionsByMode } from '@/lib/stores/studio';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import {
  Plus,
  MessageSquare,
  Video,
  Image,
  FileText,
  Clock,
  Trash2,
  Star,
  Loader2,
  CloudOff,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';

// 后端项目类型
interface BackendProject {
  id: string;
  title: string;
  brief: string;
  state: string;
  created_at: string;
  updated_at: string;
}

export default function StudioSidebar() {
  const mode = useStudioStore((state) => state.mode);
  const currentSessionId = useStudioStore((state) => state.currentSessionId);
  const createSession = useStudioStore((state) => state.createSession);
  const switchSession = useStudioStore((state) => state.switchSession);
  const deleteSession = useStudioStore((state) => state.deleteSession);
  const sessions = useStudioStore((state) => state.sessions);
  const assets = useStudioStore((state) => state.assets);
  const setSessionBackendId = useStudioStore((state) => state.setSessionBackendId);

  const [activeTab, setActiveTab] = useState<'sessions' | 'assets'>('sessions');

  // 从后端加载创意项目历史
  const backendProjectsQuery = useQuery({
    queryKey: ['creativeProjects'],
    enabled: mode === 'creative',
    queryFn: async () => {
      const res = await fetch('/api/creative/projects');
      if (!res.ok) throw new Error('获取项目列表失败');
      const data = await res.json();
      return (data.projects || []) as BackendProject[];
    },
  });

  // 使用 useMemo 缓存筛选结果,避免无限渲染
  const filteredSessions = useMemo(() => {
    return (sessions || []).filter((s) => s.mode === mode);
  }, [sessions, mode]);
  
  // 安全的资产列表
  const safeAssets = useMemo(() => assets || [], [assets]);

  const handleNewSession = () => {
    const session = createSession(mode);
    // 自动切换到新会话
    switchSession(session.id);
  };

  // 处理从后端项目恢复会话
  const handleLoadBackendProject = (project: BackendProject) => {
    // 检查是否已有该项目的本地会话
    const existingSession = filteredSessions.find(
      s => s.backendId === project.id
    );
    
    if (existingSession) {
      switchSession(existingSession.id);
    } else {
      // 创建新会话并关联后端项目
      const session = createSession('creative', project.title);
      setSessionBackendId(session.id, project.id);
      switchSession(session.id);
    }
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
              <Image className="w-3 h-3 mr-1" />
              资产
            </Button>
          )}
        </div>
      </div>

      <Separator className="bg-border/50" />

      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto px-2 scrollbar-thin scrollbar-thumb-surface-3 scrollbar-track-transparent">
        {activeTab === 'sessions' ? (
          mode === 'creative' ? (
            <CreativeProjectList 
              localSessions={filteredSessions}
              backendProjects={backendProjectsQuery.data || []}
              isLoading={backendProjectsQuery.isLoading}
              isError={backendProjectsQuery.isError}
              currentSessionId={currentSessionId}
              onSelectLocal={switchSession}
              onSelectBackend={handleLoadBackendProject}
              onDelete={deleteSession}
            />
          ) : (
            <SessionList
              sessions={filteredSessions}
              currentSessionId={currentSessionId}
              onSelect={switchSession}
              onDelete={deleteSession}
            />
          )
        ) : (
          <AssetLibrary assets={safeAssets} />
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

// ==================== 创意项目列表（合并本地+后端） ====================
interface CreativeProjectListProps {
  localSessions: any[];
  backendProjects: BackendProject[];
  isLoading: boolean;
  isError: boolean;
  currentSessionId: string | null;
  onSelectLocal: (id: string) => void;
  onSelectBackend: (project: BackendProject) => void;
  onDelete: (id: string) => void;
}

function CreativeProjectList({
  localSessions,
  backendProjects,
  isLoading,
  isError,
  currentSessionId,
  onSelectLocal,
  onSelectBackend,
  onDelete,
}: CreativeProjectListProps) {
  // 获取已关联后端项目的本地会话 ID 集合
  const linkedBackendIds = new Set(
    localSessions.filter(s => s.backendId).map(s => s.backendId)
  );
  
  // 过滤出未关联的后端项目
  const unlinkedBackendProjects = backendProjects.filter(
    p => !linkedBackendIds.has(p.id)
  );
  
  // 状态映射显示
  const stateLabels: Record<string, string> = {
    brief_pending: '📝 草稿',
    script_pending: '✍️ 生成脚本中',
    script_review: '📖 脚本审核',
    storyboard_pending: '🎨 生成分镜中',
    storyboard_ready: '🎬 分镜就绪',
    render_pending: '🎥 渲染中',
    preview_pending: '👁️ 预览生成中',
    preview_ready: '✅ 预览就绪',
    completed: '🎉 已完成',
    failed: '❌ 失败',
    paused: '⏸️ 已暂停',
  };
  
  const hasContent = localSessions.length > 0 || unlinkedBackendProjects.length > 0;
  
  return (
    <div className="space-y-1 py-2">
      {/* 加载状态 */}
      {isLoading && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-5 h-5 text-primary animate-spin mr-2" />
          <span className="text-xs text-muted-foreground">加载项目历史...</span>
        </div>
      )}
      
      {/* 错误状态 */}
      {isError && (
        <div className="flex items-center justify-center py-4 text-yellow-600">
          <CloudOff className="w-4 h-4 mr-2" />
          <span className="text-xs">无法连接服务器</span>
        </div>
      )}
      
      {/* 空状态 */}
      {!isLoading && !hasContent && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Video className="w-12 h-12 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">暂无项目</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            点击上方按钮创建新项目
          </p>
        </div>
      )}
      
      {/* 本地会话列表（当前进行中的项目） */}
      {localSessions.length > 0 && (
        <>
          <div className="px-2 py-1">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
              当前会话
            </span>
          </div>
          {localSessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                'group relative rounded-google p-3 cursor-pointer transition-all',
                currentSessionId === session.id
                  ? 'bg-primary-container/20 border border-primary/30'
                  : 'hover:bg-surface-3/50'
              )}
              onClick={() => onSelectLocal(session.id)}
            >
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                    currentSessionId === session.id
                      ? 'bg-primary/20'
                      : 'bg-surface-3'
                  )}
                >
                  <Video className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-foreground truncate">
                    {session.title}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {session.stage ? stateLabels[session.stage] || session.stage : '草稿'}
                  </p>
                </div>
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
            </div>
          ))}
        </>
      )}
      
      {/* 后端项目历史（已保存的项目） */}
      {unlinkedBackendProjects.length > 0 && (
        <>
          <div className="px-2 py-1 mt-4">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
              历史项目
            </span>
          </div>
          {unlinkedBackendProjects.map((project) => (
            <div
              key={project.id}
              className="group relative rounded-google p-3 cursor-pointer transition-all hover:bg-surface-3/50"
              onClick={() => onSelectBackend(project)}
            >
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-surface-3">
                  <Video className="w-4 h-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-foreground truncate">
                    {project.title}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {stateLabels[project.state] || project.state}
                  </p>
                  <p className="text-[10px] text-muted-foreground/70 mt-0.5">
                    {formatDistanceToNow(new Date(project.updated_at), {
                      addSuffix: true,
                      locale: zhCN,
                    })}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ==================== 会话列表 ====================
interface SessionListProps {
  sessions: any[];
  currentSessionId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

function SessionList({
  sessions,
  currentSessionId,
  onSelect,
  onDelete,
}: SessionListProps) {
  // 安全检查
  const safeSessions = sessions || [];
  
  return (
    <div className="space-y-1 py-2">
      {safeSessions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <MessageSquare className="w-12 h-12 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">暂无历史记录</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            点击上方按钮开始新会话
          </p>
        </div>
      ) : (
        safeSessions.map((session) => (
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
  assets: any[];
}

function AssetLibrary({ assets }: AssetLibraryProps) {
  // 安全检查
  const safeAssets = assets || [];
  
  return (
    <div className="space-y-2 py-2">
      {safeAssets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Image className="w-12 h-12 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">暂无资产</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            生成的视频和图片会显示在这里
          </p>
        </div>
      ) : (
        safeAssets.map((asset) => (
          <div
            key={asset.id}
            className="group rounded-google overflow-hidden bg-surface-3/30 hover:bg-surface-3 transition-all cursor-pointer"
          >
            {/* 缩略图 */}
            {asset.thumbnailUrl && (
              <div className="aspect-video bg-surface-3 relative overflow-hidden">
                <img
                  src={asset.thumbnailUrl}
                  alt={asset.title}
                  className="w-full h-full object-cover"
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
                    <Image className="w-3 h-3 text-primary" />
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
