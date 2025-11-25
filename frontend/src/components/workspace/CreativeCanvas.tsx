/**
 * Creative Canvas - 视频生成全流程
 * Drafting -> Scripting -> Visualizing -> Rendering -> Done
 */

'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useStudioStore } from '@/lib/stores/studio';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  Video,
  Wand2,
  Film,
  Image,
  Download,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

type Stage = 'drafting' | 'scripting' | 'visualizing' | 'rendering' | 'done';

interface CreativeProject {
  id: string;
  title: string;
  brief: string;
  duration_seconds: number;
  style: string;
  state: string;
  script?: string | null;
  storyboard?: { scene_number: number; description: string; visual_reference_path?: string | null }[];
  shots?: { scene_number: number; video_url?: string | null; status?: string }[];
  render_manifest?: any;
  preview_record?: any;
}

export default function CreativeCanvas() {
  const searchParams = useSearchParams();
  const urlProjectId = searchParams.get('project');
  
  const setCreativeStage = useStudioStore((state) => state.setCreativeStage);
  const currentSessionId = useStudioStore((state) => state.currentSessionId);
  const sessions = useStudioStore((state) => state.sessions);
  const setSessionBackendId = useStudioStore((state) => state.setSessionBackendId);
  
  // 从当前 session 获取 backendId（即 projectId），或从 URL 参数获取
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const savedProjectId = currentSession?.backendId || urlProjectId;
  
  const [stage, setStage] = useState<Stage>('drafting');
  const [projectId, setProjectId] = useState<string | null>(savedProjectId || null);
  const [prompt, setPrompt] = useState('');
  const [error, setError] = useState<string>('');
  const queryClient = useQueryClient();
  
  // 当 savedProjectId 变化时同步（如切换 session 或 URL 参数变化）
  useEffect(() => {
    if (savedProjectId && savedProjectId !== projectId) {
      setProjectId(savedProjectId);
      // 如果是从 URL 加载的，同步到 session
      if (urlProjectId && currentSessionId && !currentSession?.backendId) {
        setSessionBackendId(currentSessionId, urlProjectId);
      }
    }
  }, [savedProjectId, urlProjectId, currentSessionId, currentSession?.backendId]);

  const projectQuery = useQuery({
    queryKey: ['creativeProject', projectId],
    enabled: !!projectId,
    refetchInterval: (query) => {
      const state = (query.state.data?.project?.state as string) || '';
      // 稳定状态停止轮询：completed, storyboard_ready, script_ready
      const stableStates = ['completed', 'storyboard_ready', 'script_ready'];
      return stableStates.includes(state) ? false : 2000;
    },
    queryFn: async () => {
      const res = await fetch(`/api/creative/projects/${projectId}`);
      if (!res.ok) throw new Error('获取项目失败');
      return res.json() as Promise<{ project: CreativeProject }>;
    },
  });

  const project = projectQuery.data?.project;

  // 根据后端状态推进阶段
  useEffect(() => {
    if (!project) return;
    
    // 根据后端状态映射前端阶段
    const state = project.state;
    
    if (state === 'completed') {
      setStage('done');
      setCreativeStage('done');
      return;
    }
    
    // 视频渲染中或渲染完成
    if (state === 'rendering' || state === 'render_pending' || 
        (project.shots && project.shots.length > 0)) {
      setStage('rendering');
      setCreativeStage('rendering');
      return;
    }
    
    // 分镜已生成（storyboard_ready）- 显示分镜预览
    if (state === 'storyboard_ready' || 
        (project.storyboard && project.storyboard.length > 0)) {
      setStage('visualizing');
      setCreativeStage('visualizing');
      return;
    }
    
    // 脚本已生成 - 等待批准脚本
    if (state === 'script_ready' || project.script) {
      setStage('scripting');
      setCreativeStage('scripting');
      return;
    }
  }, [project, setCreativeStage]);

  const handleDraftGenerate = async () => {
    if (!prompt.trim()) return;
    setError('');
    try {
      const res = await fetch('/api/creative/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: prompt.slice(0, 50),
          brief: prompt,
          duration_seconds: 15,
          style: 'cinematic',
        }),
      });
      if (!res.ok) throw new Error('创建项目失败');
      const data = await res.json();
      const newProjectId = data.project.id;
      setProjectId(newProjectId);
      // 保存 projectId 到 session，这样刷新后能恢复
      if (currentSessionId) {
        setSessionBackendId(currentSessionId, newProjectId);
      }
      setStage('scripting');
      setCreativeStage('scripting');
      queryClient.invalidateQueries({ queryKey: ['creativeProject', newProjectId] });
    } catch (e: any) {
      setError(e?.message || '创建失败');
    }
  };

  const handleAdvance = async () => {
    if (!projectId) return;
    setError('');
    try {
      const res = await fetch(`/api/creative/projects/${projectId}/advance`, {
        method: 'POST',
        signal: AbortSignal.timeout(120000), // 2分钟超时
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || '推进流程失败');
      }
      queryClient.invalidateQueries({ queryKey: ['creativeProject', projectId] });
    } catch (e: any) {
      if (e.name === 'TimeoutError') {
        setError('请求超时，请稍后刷新页面查看结果');
      } else {
        setError(e?.message || '操作失败');
      }
    }
  };

  const shots = useMemo(() => project?.shots || [], [project]);

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
              />
            )}
            {stage === 'scripting' && (
              <ScriptingStage project={project} onAdvance={handleAdvance} />
            )}
            {stage === 'visualizing' && (
              <VisualizingStage project={project} onAdvance={handleAdvance} />
            )}
            {stage === 'rendering' && (
              <RenderingStage project={project} onAdvance={handleAdvance} />
            )}
            {stage === 'done' && <DoneStage shots={shots} />}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

// ==================== 阶段进度条 ====================
const STAGES = [
  { id: 'drafting', label: '概念撰写', icon: Wand2 },
  { id: 'scripting', label: '脚本生成', icon: Film },
  { id: 'visualizing', label: '分镜生成', icon: Image },
  { id: 'rendering', label: '视频渲染', icon: Video },
  { id: 'done', label: '完成', icon: CheckCircle2 },
] as const;

function StageProgress({ currentStage }: { currentStage: string }) {
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
}: {
  prompt: string;
  onPromptChange: (v: string) => void;
  onGenerate: () => void;
}) {
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
        />

        <div className="flex items-center justify-between">
          <div className="text-xs text-muted-foreground">{prompt.length} / 2000 字符</div>
          <Button
            onClick={onGenerate}
            disabled={!prompt.trim()}
            className="bg-primary hover:bg-primary/90 rounded-google"
          >
            <Wand2 className="w-4 h-4 mr-2" />
            创建项目
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

// ==================== 阶段 2: 脚本生成 ====================
function ScriptingStage({
  project,
  onAdvance,
}: {
  project?: CreativeProject;
  onAdvance: () => void;
}) {
  const [isAdvancing, setIsAdvancing] = useState(false);

  const handleAdvance = async () => {
    setIsAdvancing(true);
    try {
      await onAdvance();
    } finally {
      setIsAdvancing(false);
    }
  };

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
            {project?.script 
              ? '脚本已生成，确认后点击右侧按钮生成分镜图片' 
              : 'AI 正在生成脚本，请稍候...'}
          </p>
        </div>
        <Button 
          onClick={handleAdvance} 
          disabled={!project?.script || isAdvancing} 
          className="bg-primary hover:bg-primary/90 rounded-google"
        >
          {isAdvancing ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Image className="w-4 h-4 mr-2" />
          )}
          {isAdvancing ? '生成中...' : '生成分镜图片'}
        </Button>
      </div>

      <div className="bg-surface-2 rounded-google-lg p-5 border border-border/30">
        {project?.script ? (
          <pre className="text-sm whitespace-pre-wrap text-foreground leading-relaxed">{project.script}</pre>
        ) : (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
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
}: {
  project?: CreativeProject;
  onAdvance: () => void;
}) {
  const panels = project?.storyboard || [];
  const [imageErrors, setImageErrors] = useState<Set<number>>(new Set());
  const [isAdvancing, setIsAdvancing] = useState(false);

  const handleAdvance = async () => {
    setIsAdvancing(true);
    try {
      await onAdvance();
    } finally {
      setIsAdvancing(false);
    }
  };

  const handleImageError = (sceneNumber: number) => {
    setImageErrors(prev => new Set(prev).add(sceneNumber));
  };

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
            已生成 {panels.length} 个场景，查看视觉效果后可开始渲染
          </p>
        </div>
        <Button 
          onClick={handleAdvance} 
          disabled={panels.length === 0 || isAdvancing}
          className="bg-primary hover:bg-primary/90 rounded-google"
        >
          {isAdvancing ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Video className="w-4 h-4 mr-2" />
          )}
          {isAdvancing ? '提交中...' : '开始渲染视频'}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {panels.length === 0 && (
          <div className="col-span-2 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在生成分镜...
          </div>
        )}
        {panels.map((panel) => (
          <div
            key={panel.scene_number}
            className="group aspect-video bg-surface-3 rounded-google-lg overflow-hidden border border-border/30 relative"
          >
            {panel.visual_reference_path && !imageErrors.has(panel.scene_number) ? (
              <img
                src={panel.visual_reference_path}
                alt={panel.description}
                className="w-full h-full object-cover"
                onError={() => handleImageError(panel.scene_number)}
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface-3">
                {imageErrors.has(panel.scene_number) ? (
                  <>
                    <AlertCircle className="w-6 h-6 text-muted-foreground mb-2" />
                    <span className="text-xs text-muted-foreground">图片已过期</span>
                  </>
                ) : (
                  <Loader2 className="w-6 h-6 text-muted-foreground animate-spin" />
                )}
              </div>
            )}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-3">
              <p className="text-xs text-white font-medium">场景 {panel.scene_number}</p>
              <p className="text-xs text-white/80 line-clamp-2 mt-1">{panel.description}</p>
            </div>
          </div>
        ))}
      </div>

      {imageErrors.size > 0 && (
        <div className="text-xs text-amber-500 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          部分图片链接已过期（豆包图片24小时有效），但不影响视频渲染
        </div>
      )}
    </motion.div>
  );
}

// ==================== 阶段 4: 视频渲染 ====================
function RenderingStage({
  project,
  onAdvance,
}: {
  project?: CreativeProject;
  onAdvance: () => void;
}) {
  const state = project?.state || 'render_pending';
  const shots = project?.shots || [];
  const completed = shots.filter((s) => s.status === 'completed').length;

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
            {state === 'completed'
              ? '渲染完成，进入预览'
              : 'AI 正在合成视频，稍候自动更新状态'}
          </p>
        </div>
        <Button onClick={onAdvance} className="bg-primary hover:bg-primary/90 rounded-google">
          刷新进度
        </Button>
      </div>

      <div className="bg-surface-2 rounded-google-lg p-6 space-y-3">
        <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-primary"
            initial={{ width: '0%' }}
            animate={{ width: `${shots.length ? (completed / shots.length) * 100 : 40}%` }}
            transition={{ duration: 0.6, ease: 'easeInOut' }}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {shots.length ? `${completed}/${shots.length} 片段完成` : '准备渲染素材...'}
        </p>
      </div>
    </motion.div>
  );
}

// ==================== 阶段 5: 完成 ====================
function DoneStage({ shots }: { shots: any[] }) {
  const firstVideo = shots.find((s) => s.video_url)?.video_url;
  const [videoError, setVideoError] = useState(false);

  const handleDownload = async () => {
    if (!firstVideo) return;
    try {
      const response = await fetch(firstVideo);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `video-${Date.now()}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert('下载失败，视频链接可能已过期');
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
        <h2 className="text-2xl font-bold text-foreground">视频生成完成！</h2>
        <p className="text-sm text-muted-foreground">你的视频已经准备好，点击播放预览。</p>
      </div>

      <div className="bg-surface-2 rounded-google-lg p-6 space-y-4">
        <div className="aspect-video bg-surface-3 rounded-google overflow-hidden">
          {firstVideo && !videoError ? (
            <video 
              src={firstVideo} 
              controls 
              className="w-full h-full object-cover"
              onError={() => setVideoError(true)}
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center">
              <Video className="w-10 h-10 text-muted-foreground mb-2" />
              <span className="text-sm text-muted-foreground">
                {videoError ? '视频链接已过期' : '暂无视频'}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center justify-center gap-3">
          {firstVideo && !videoError && (
            <Button 
              onClick={handleDownload}
              variant="outline" 
              className="rounded-google"
            >
              <Download className="w-4 h-4 mr-2" />
              下载视频
            </Button>
          )}
        </div>

        {/* 显示所有视频片段 */}
        {shots.length > 1 && (
          <div className="pt-4 border-t border-border/30">
            <h3 className="text-sm font-medium text-foreground mb-3">全部片段 ({shots.length})</h3>
            <div className="grid grid-cols-3 gap-2">
              {shots.map((shot, idx) => (
                <div key={idx} className="aspect-video bg-surface-3 rounded overflow-hidden">
                  {shot.video_url ? (
                    <video src={shot.video_url} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <span className="text-xs text-muted-foreground">片段 {idx + 1}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
