/**
 * Creative Canvas - 视频生成全流程
 * Drafting -> Scripting -> Visualizing -> Rendering -> Done
 */

'use client';

import { AnimatePresence, motion } from 'framer-motion';
import NextImage from 'next/image';
import { useEffect, useMemo, useRef, useState, type JSX } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Film,
  Image as ImageIcon,
  Loader2,
  Video,
  Wand2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import type { CreativeProject, GeneratedShot, StoryboardPanel } from '@/lib/api';
import { useStudioStore } from '@/lib/stores/studio';
import { cn } from '@/lib/utils';

type Stage = 'drafting' | 'scripting' | 'visualizing' | 'rendering' | 'done';

export default function CreativeCanvas(): JSX.Element {
  const setCreativeStage = useStudioStore((state) => state.setCreativeStage);
  const [stage, setStage] = useState<Stage>('drafting');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const queryClient = useQueryClient();

  const projectQuery = useQuery<{ project: CreativeProject }>({
    queryKey: ['creativeProject', projectId],
    enabled: Boolean(projectId),
    refetchInterval: (data) => {
      const state = data?.project?.state ?? '';
      // Stop polling when completed or in review states
      if (state === 'completed') return false;
      return 2000;
    },
    queryFn: async () => {
      const res = await fetch(`/api/creative/projects/${projectId}`);
      if (!res.ok) throw new Error('获取项目失败');
      return res.json() as Promise<{ project: CreativeProject }>;
    },
  });

  const project = projectQuery.data?.project;

  // Map backend states to frontend stages
  useEffect(() => {
    if (!project) return;
    
    const backendState = project.state;
    
    // Map backend states to UI stages
    if (backendState === 'completed') {
      setStage('done');
      setCreativeStage('done');
    } else if (backendState === 'render_pending' || backendState === 'preview_pending' || 
               backendState === 'preview_ready' || backendState === 'validation_pending' ||
               backendState === 'distribution_pending') {
      setStage('rendering');
      setCreativeStage('rendering');
    } else if (backendState === 'storyboard_pending' || backendState === 'storyboard_ready') {
      setStage('visualizing');
      setCreativeStage('visualizing');
    } else if (backendState === 'script_pending' || backendState === 'script_review') {
      setStage('scripting');
      setCreativeStage('scripting');
    } else if (backendState === 'brief_pending') {
      setStage('drafting');
      setCreativeStage('drafting');
    }
    
    // Clear loading state when data arrives
    setIsLoading(false);
  }, [project, setCreativeStage]);

  const handleDraftGenerate = async (): Promise<void> => {
    if (!prompt.trim()) return;
    setError('');
    setIsLoading(true);
    try {
      const res = await fetch('/api/creative/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: prompt.slice(0, 50),
          brief: prompt,
          duration_seconds: 30,
          style: 'cinematic',
        }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || '创建项目失败');
      }
      const data = await res.json();
      setProjectId(data.project.id);
      setStage('scripting');
      setCreativeStage('scripting');
      await queryClient.invalidateQueries({ queryKey: ['creativeProject', data.project.id] });
    } catch (e) {
      const message = e instanceof Error ? e.message : '创建失败';
      setError(message);
      setIsLoading(false);
    }
  };

  // Approve script and generate storyboard
  const handleApproveScript = async (): Promise<void> => {
    if (!projectId) return;
    setError('');
    setIsLoading(true);
    try {
      const res = await fetch(`/api/creative/projects/${projectId}/approve-script`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || '生成分镜失败');
      }
      await queryClient.invalidateQueries({ queryKey: ['creativeProject', projectId] });
    } catch (e) {
      const message = e instanceof Error ? e.message : '生成分镜失败';
      setError(message);
      setIsLoading(false);
    }
  };

  // Advance to next stage (for rendering etc.)
  const handleAdvance = async (): Promise<void> => {
    if (!projectId) return;
    setError('');
    setIsLoading(true);
    try {
      const res = await fetch(`/api/creative/projects/${projectId}/advance`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || '推进流程失败');
      }
      await queryClient.invalidateQueries({ queryKey: ['creativeProject', projectId] });
    } catch (e) {
      const message = e instanceof Error ? e.message : '推进流程失败';
      setError(message);
      setIsLoading(false);
    }
  };

  const shots = useMemo(() => project?.shots ?? [], [project]);

  return (
    <div className="h-full flex flex-col bg-surface-1">
      <StageProgress currentStage={stage} />

      <div className="flex-1 overflow-y-auto px-6 py-8 scrollbar-thin scrollbar-thumb-surface-3 scrollbar-track-transparent">
        <div className="max-w-4xl mx-auto">
          {error && (
            <div className="mb-4 flex items-center gap-2 text-red-500 text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
          <AnimatePresence mode="wait">
            {stage === 'drafting' && (
              <DraftingStage
                prompt={prompt}
                onPromptChange={setPrompt}
                onGenerate={handleDraftGenerate}
                isLoading={isLoading}
              />
            )}
            {stage === 'scripting' && (
              <ScriptingStage 
                project={project} 
                onApproveScript={handleApproveScript}
                isLoading={isLoading}
              />
            )}
            {stage === 'visualizing' && (
              <VisualizingStage 
                project={project} 
                onAdvance={handleAdvance}
                isLoading={isLoading}
              />
            )}
            {stage === 'rendering' && (
              <RenderingStage 
                project={project} 
                onAdvance={handleAdvance}
                isLoading={isLoading}
              />
            )}
            {stage === 'done' && <DoneStage shots={shots} />}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

// ==================== 阶段进度 ====================
const STAGES = [
  { id: 'drafting', label: '概念撰写', icon: Wand2 },
  { id: 'scripting', label: '脚本生成', icon: Film },
  { id: 'visualizing', label: '分镜生成', icon: ImageIcon },
  { id: 'rendering', label: '视频渲染', icon: Video },
  { id: 'done', label: '完成', icon: CheckCircle2 },
] as const;

function StageProgress({ currentStage }: { currentStage: Stage }): JSX.Element {
  const currentIndex = STAGES.findIndex((s) => s.id === currentStage);

  return (
    <div className="border-b border-border/30 bg-surface-2/50 backdrop-blur-sm px-6 py-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between">
          {STAGES.map((stage, index) => {
            const Icon = stage.icon;
            const isActive = index === currentIndex;
            const isCompleted = index < currentIndex;

            return (
              <div key={stage.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center gap-2">
                  <div
                    className={cn(
                      'w-10 h-10 rounded-full flex items-center justify-center transition-all',
                      isActive &&
                        'bg-primary text-primary-foreground shadow-lg scale-110',
                      isCompleted &&
                        'bg-primary/20 text-primary',
                      !isActive && !isCompleted && 'bg-surface-3 text-muted-foreground'
                    )}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <span
                    className={cn(
                      'text-xs font-medium transition-colors',
                      isActive && 'text-foreground',
                      isCompleted && 'text-primary',
                      !isActive && !isCompleted && 'text-muted-foreground'
                    )}
                  >
                    {stage.label}
                  </span>
                </div>

                {/* 进度线 */}
                {index < STAGES.length - 1 && (
                  <div className="flex-1 h-0.5 mx-2 mt-[-20px]">
                    <div
                      className={cn(
                        'h-full transition-colors',
                        isCompleted ? 'bg-primary' : 'bg-surface-3'
                      )}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ==================== 阶段 1: 概念撰写 ====================
function DraftingStage({
  prompt,
  onPromptChange,
  onGenerate,
  isLoading,
}: {
  prompt: string;
  onPromptChange: (v: string) => void;
  onGenerate: () => Promise<void>;
  isLoading: boolean;
}): JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold text-foreground">描述你的视频需求</h2>
        <p className="text-sm text-muted-foreground">
          详细说明视频内容、风格和目标，AI 将为你生成专业分镜与脚本。
        </p>
      </div>

      <div className="bg-surface-2 rounded-google-lg p-6 space-y-4">
        <Textarea
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="示例：30 秒产品宣传片，展示 AI 助理提升办公效率，强调安全与隐私..."
          className="min-h-[200px] bg-surface-1 border-border/50 rounded-google"
          disabled={isLoading}
        />

        <div className="flex items-center justify-between">
          <div className="text-xs text-muted-foreground">{prompt.length} / 2000 字符</div>
          <Button
            onClick={() => {
              void onGenerate();
            }}
            disabled={!prompt.trim() || isLoading}
            className="bg-primary hover:bg-primary/90 rounded-google"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                创建中...
              </>
            ) : (
              <>
                <Wand2 className="w-4 h-4 mr-2" />
                创建项目
              </>
            )}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

// ==================== 阶段 2: 脚本生成 ====================
function ScriptingStage({
  project,
  onApproveScript,
  isLoading,
}: {
  project?: CreativeProject;
  onApproveScript: () => Promise<void>;
  isLoading: boolean;
}): JSX.Element {
  const hasScript = Boolean(project?.script);
  const canApprove = hasScript && project?.state === 'script_review';
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">分镜脚本</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {hasScript ? '脚本已生成，确认后继续生成分镜。' : 'AI 正在生成脚本，请稍候...'}
          </p>
        </div>
        <Button
          onClick={() => {
            void onApproveScript();
          }}
          disabled={!canApprove || isLoading}
          className="bg-primary hover:bg-primary/90 rounded-google"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              生成中...
            </>
          ) : (
            <>
              <ImageIcon className="w-4 h-4 mr-2" />
              确认并生成分镜
            </>
          )}
        </Button>
      </div>

      <div className="bg-surface-2 rounded-google-lg p-5 border border-border/30">
        {project?.script ? (
          <pre className="text-sm whitespace-pre-wrap text-foreground">{project.script}</pre>
        ) : (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在生成脚本...
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ==================== 阶段 3: 分镜生成 ====================
function VisualizingStage({
  project,
  onAdvance,
  isLoading,
}: {
  project?: CreativeProject;
  onAdvance: () => Promise<void>;
  isLoading: boolean;
}): JSX.Element {
  const panels: StoryboardPanel[] = project?.storyboard ?? [];
  const isGenerating = project?.state === 'storyboard_pending';
  const canAdvance = panels.length > 0 && project?.state === 'storyboard_ready';
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">分镜预览</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {isGenerating ? '正在生成分镜，请稍候...' : '查看每个场景的视觉效果。'}
          </p>
        </div>
        <Button
          onClick={() => {
            void onAdvance();
          }}
          disabled={!canAdvance || isLoading}
          className="bg-primary hover:bg-primary/90 rounded-google"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              处理中...
            </>
          ) : (
            <>
              <Video className="w-4 h-4 mr-2" />
              开始渲染视频
            </>
          )}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {panels.length === 0 && (
          <div className="col-span-2 flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在生成分镜...
          </div>
        )}
        {panels.map((panel) => (
          <div
            key={panel.scene_number}
            className="group aspect-video bg-surface-3 rounded-google-lg overflow-hidden border border-border/30 relative"
          >
            {panel.visual_reference_path ? (
              <NextImage
                src={panel.visual_reference_path}
                alt={panel.description}
                fill
                className="object-cover"
                sizes="(min-width: 1024px) 50vw, 100vw"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="w-6 h-6 text-muted-foreground animate-spin" />
              </div>
            )}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-white/70">场景 {panel.scene_number}</span>
                <span className="text-xs text-white/50">·</span>
                <span className="text-xs text-white/70">{panel.duration_seconds}秒</span>
              </div>
              <p className="text-xs text-white line-clamp-2">{panel.description}</p>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ==================== 阶段 4: 视频渲染 ====================
function RenderingStage({
  project,
  onAdvance,
  isLoading,
}: {
  project?: CreativeProject;
  onAdvance: () => Promise<void>;
  isLoading: boolean;
}): JSX.Element {
  const state = project?.state ?? 'render_pending';
  const shots: GeneratedShot[] = project?.shots ?? [];
  const completed = shots.filter((s) => s.status === 'completed').length;
  const isCompleted = state === 'completed';
  
  // Calculate progress based on state
  const getProgressPercentage = () => {
    if (isCompleted) return 100;
    if (shots.length > 0) return (completed / shots.length) * 100;
    if (state === 'render_pending') return 20;
    if (state === 'preview_pending') return 60;
    if (state === 'preview_ready') return 80;
    if (state === 'validation_pending') return 90;
    return 40;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="flex flex-col gap-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">视频渲染中</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {isCompleted ? '渲染完成！' : 'AI 正在合成视频，稍候自动更新状态。'}
          </p>
        </div>
        <Button
          onClick={() => {
            void onAdvance();
          }}
          disabled={isLoading}
          variant="outline"
          className="rounded-google"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            '刷新进度'
          )}
        </Button>
      </div>

      <div className="bg-surface-2 rounded-google-lg p-6 space-y-3">
        <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-primary"
            initial={{ width: '0%' }}
            animate={{ width: `${getProgressPercentage()}%` }}
            transition={{ duration: 0.6, ease: 'easeInOut' }}
          />
        </div>
        <div className="flex justify-between items-center">
          <p className="text-xs text-muted-foreground">
            {shots.length > 0 ? `${completed}/${shots.length} 片段完成` : '准备渲染素材...'}
          </p>
          <p className="text-xs text-muted-foreground capitalize">
            状态: {state.replace(/_/g, ' ')}
          </p>
        </div>
      </div>
      
      {/* Show shot previews if available */}
      {shots.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {shots.slice(0, 6).map((shot) => (
            <div key={shot.scene_number} className="aspect-video bg-surface-3 rounded-google overflow-hidden relative">
              {shot.video_url ? (
                <video src={shot.video_url} className="w-full h-full object-cover" muted />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  {shot.status === 'processing' ? (
                    <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
                  ) : shot.status === 'failed' ? (
                    <AlertCircle className="w-5 h-5 text-red-500" />
                  ) : (
                    <Video className="w-5 h-5 text-muted-foreground" />
                  )}
                </div>
              )}
              <div className="absolute bottom-0 left-0 right-0 bg-black/50 px-2 py-1">
                <span className="text-[10px] text-white">场景 {shot.scene_number}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// ==================== 阶段 5: 完成 ====================
function DoneStage({ shots }: { shots: GeneratedShot[] }): JSX.Element {
  const firstVideo = shots.find((s) => s.video_url)?.video_url;
  const [isPlaying, setIsPlaying] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const handlePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        void videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <div className="w-16 h-16 bg-primary/10 rounded-google-lg flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold text-foreground">视频生成完成</h2>
        <p className="text-sm text-muted-foreground">你的视频已经准备好。</p>
      </div>

      <div className="bg-surface-2 rounded-google-lg p-6 space-y-4">
        <div className="aspect-video bg-surface-3 rounded-google overflow-hidden">
          {firstVideo ? (
            <video 
              ref={videoRef}
              src={firstVideo} 
              controls 
              className="w-full h-full object-cover"
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-center p-4">
              <Video className="w-10 h-10 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">视频处理中或暂无可用视频</p>
              <p className="text-xs text-muted-foreground mt-1">请稍后刷新查看</p>
            </div>
          )}
        </div>

        {firstVideo && (
          <div className="flex items-center justify-center gap-3">
            <Button 
              onClick={handlePlay}
              className="bg-primary hover:bg-primary/90 rounded-google"
            >
              {isPlaying ? '暂停' : '播放'}视频
            </Button>
            <Button 
              variant="outline" 
              className="rounded-google"
              onClick={() => {
                if (firstVideo) {
                  window.open(firstVideo, '_blank');
                }
              }}
            >
              <Download className="w-4 h-4 mr-2" />
              新窗口打开
            </Button>
          </div>
        )}
      </div>
      
      {/* 显示所有视频片段 */}
      {shots.length > 1 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-foreground">所有片段</h3>
          <div className="grid grid-cols-3 gap-3">
            {shots.map((shot) => (
              <div key={shot.scene_number} className="aspect-video bg-surface-3 rounded-google overflow-hidden relative">
                {shot.video_url ? (
                  <video 
                    src={shot.video_url} 
                    className="w-full h-full object-cover cursor-pointer" 
                    muted
                    onClick={() => shot.video_url && window.open(shot.video_url, '_blank')}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Video className="w-5 h-5 text-muted-foreground" />
                  </div>
                )}
                <div className="absolute bottom-0 left-0 right-0 bg-black/50 px-2 py-1">
                  <span className="text-[10px] text-white">场景 {shot.scene_number}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
