/**
 * General Canvas - 通用对话界面
 * 真实流式聊天 + 工具调用卡片
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { useStudioStore, selectCurrentSession } from '@/lib/stores/studio';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  Send,
  Loader2,
  User,
  Bot,
  Search,
  Code,
  ChevronDown,
  ChevronUp,
  Paperclip,
  X,
  FileText,
  Image as ImageIcon,
  Square,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function uuid() {
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function GeneralCanvas() {
  const createSession = useStudioStore((state) => state.createSession);
  const setSessionBackendId = useStudioStore(
    (state) => state.setSessionBackendId
  );
  const addMessage = useStudioStore((state) => state.addMessage);
  const currentSessionId = useStudioStore((state) => state.currentSessionId);
  const isStreaming = useStudioStore((state) => state.isStreaming);
  const setStreaming = useStudioStore((state) => state.setStreaming);
  const currentSession = useStudioStore(selectCurrentSession);

  const [input, setInput] = useState('');
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [statusText, setStatusText] = useState<string>('AI 正在思考...');
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [currentSession?.messages]);

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  const ensureSession = () => {
    if (!currentSession) {
      return createSession('general', 'General Chat');
    }
    return currentSession;
  };

  const ensureBackendSession = async (
    goal: string,
    sessionId: string
  ): Promise<string> => {
    const localSession = useStudioStore
      .getState()
      .sessions.find((s) => s.id === sessionId);
    if (localSession?.backendId) return localSession.backendId;

    const res = await fetch('/api/general/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, tenant_id: 'demo' }),
    });
    if (!res.ok) throw new Error('创建会话失败');
    const data = await res.json();
    const backendId = data?.session?.id;
    if (!backendId) throw new Error('未获取到会话 ID');
    setSessionBackendId(sessionId, backendId);
    return backendId;
  };

  const handleSSEEvent = (data: any, sessionId: string) => {
    if (data.status === 'thinking') {
      setStatusText('AI 正在思考...');
      return;
    }
    if (data.status === 'processing') {
      setStatusText('AI 正在调用工具...');
      return;
    }
    if (data.status === 'completed') {
      const sessionData = data.session;
      const assistantText =
        sessionData?.summary ||
        (sessionData?.messages || []).slice(-1)[0] ||
        '完成';
      addMessage(sessionId, {
        role: 'assistant',
        content: assistantText,
        toolCalls: sessionData?.tool_calls,
      });
      setStreaming(false);
      setStatusText('');
      return;
    }
    if (data.status === 'error') {
      addMessage(sessionId, {
        role: 'assistant',
        content: data.message || '生成失败',
      });
      setStreaming(false);
      setStatusText('');
    }
  };

  const handleSend = async () => {
    if ((!input.trim() && attachedFiles.length === 0) || isStreaming) return;

    const session = ensureSession();
    const text = input.trim();
    const files = [...attachedFiles];
    setInput('');
    setAttachedFiles([]);
    setStreaming(true);
    setStatusText('AI 正在思考...');

    // 显示用户消息（包含附件信息）
    const userContent = files.length > 0
      ? `${text}\n\n📎 附件: ${files.map(f => f.name).join(', ')}`
      : text;

    addMessage(session.id, {
      role: 'user',
      content: userContent,
    });

    try {
      const backendId = await ensureBackendSession(text || '处理上传的文件', session.id);
      const form = new FormData();
      form.append('prompt', text);
      
      // 添加文件到 FormData
      files.forEach((file) => {
        form.append('files', file);
      });

      const controller = new AbortController();
      abortRef.current = controller;

      const res = await fetch(`/api/general/sessions/${backendId}/message`, {
        method: 'POST',
        body: form,
        signal: controller.signal,
      });

      if (!res.body) {
        throw new Error('未收到流式响应');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const flushEvents = (chunk: string) => {
        buffer += chunk;
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);
          if (!raw.startsWith('data:')) continue;
          try {
            const payload = JSON.parse(raw.replace(/^data:\s*/, ''));
            handleSSEEvent(payload, session.id);
          } catch (e) {
            console.error('解析 SSE 失败', e);
          }
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          flushEvents('');
          break;
        }
        const chunk = decoder.decode(value, { stream: true });
        flushEvents(chunk);
      }
    } catch (e: any) {
      console.error(e);
      addMessage(session.id, {
        role: 'assistant',
        content: e?.message || '发送失败',
      });
      setStreaming(false);
      setStatusText('');
    } finally {
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleAbort = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setStreaming(false);
      setStatusText('');
      if (currentSession) {
        addMessage(currentSession.id, {
          role: 'assistant',
          content: '⚠️ 回答已被用户中断',
        });
      }
    }
  };

  const toggleToolExpansion = (toolId: string) => {
    setExpandedTools((prev) => {
      const next = new Set(prev);
      if (next.has(toolId)) {
        next.delete(toolId);
      } else {
        next.add(toolId);
      }
      return next;
    });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const newFiles = Array.from(files).slice(0, 5 - attachedFiles.length); // 最多5个文件
      setAttachedFiles((prev) => [...prev, ...newFiles]);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const getFileIcon = (file: File) => {
    if (file.type.startsWith('image/')) return ImageIcon;
    return FileText;
  };

  return (
    <div className="h-full flex flex-col bg-surface-1">
      {/* 信息列表 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {!currentSession || currentSession.messages.length === 0 ? (
            <EmptyState />
          ) : (
            <AnimatePresence mode="popLayout">
              {currentSession.messages.map((message, index) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.2 }}
                >
                  <MessageBubble message={message} />

                  {/* Tool Invocations */}
                  {message.toolCalls &&
                    message.toolCalls.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {message.toolCalls.map((tool, toolIndex) => (
                          <ToolInvocationCard
                            key={`${message.id}-tool-${toolIndex}`}
                            tool={tool}
                            isExpanded={expandedTools.has(
                              `${message.id}-${toolIndex}`
                            )}
                            onToggle={() =>
                              toggleToolExpansion(`${message.id}-${toolIndex}`)
                            }
                          />
                        ))}
                      </div>
                    )}
                </motion.div>
              ))}
            </AnimatePresence>
          )}

          {/* 流式状态指示条 */}
          {isStreaming && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-start gap-3"
            >
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="flex-1 bg-surface-2 rounded-google-lg p-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{statusText}</span>
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* 输入区 */}
      <div className="border-t border-border/30 bg-surface-2/50 backdrop-blur-sm p-4">
        <div className="max-w-3xl mx-auto">
          {/* 附件预览区 */}
          {attachedFiles.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {attachedFiles.map((file, index) => {
                const Icon = getFileIcon(file);
                return (
                  <div
                    key={index}
                    className="flex items-center gap-2 bg-surface-3 rounded-google px-3 py-1.5 text-sm"
                  >
                    <Icon className="w-4 h-4 text-primary" />
                    <span className="text-foreground truncate max-w-[150px]">
                      {file.name}
                    </span>
                    <button
                      onClick={() => removeFile(index)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          <div className="relative">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="请输入你的问题、任务或代码... (Shift + Enter 换行)"
              className="min-h-[80px] max-h-[200px] pr-24 rounded-google-lg bg-surface-1 border-border/50 focus-visible:ring-primary resize-none"
              disabled={isStreaming}
            />
            
            {/* 文件上传按钮 */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.txt,.md,.json,.csv,.py,.js,.ts,.html,.css"
              onChange={handleFileSelect}
              className="hidden"
            />
            <Button
              size="icon"
              variant="ghost"
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || attachedFiles.length >= 5}
              className="absolute right-14 bottom-2 rounded-full hover:bg-surface-3"
              title="上传文件 (最多5个)"
            >
              <Paperclip className="w-4 h-4 text-muted-foreground" />
            </Button>

            {isStreaming ? (
              <Button
                size="icon"
                onClick={handleAbort}
                className="absolute right-2 bottom-2 rounded-full bg-destructive hover:bg-destructive/90"
                title="停止生成"
              >
                <Square className="w-4 h-4 fill-current" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={handleSend}
                disabled={!input.trim() && attachedFiles.length === 0}
                className="absolute right-2 bottom-2 rounded-full bg-primary hover:bg-primary/90"
              >
                <Send className="w-4 h-4" />
              </Button>
            )}
          </div>

          <div className="mt-2 text-xs text-muted-foreground text-center">
            Lewis AI 会实时推理与调用工具，结果将流式返回 | 支持上传图片和文档
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== 信息气泡 ====================
function MessageBubble({ message }: { message: any }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          isUser ? 'bg-primary/20' : 'bg-surface-3'
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-primary" />
        ) : (
          <Bot className="w-4 h-4 text-primary" />
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          'flex-1 rounded-google-lg p-4 max-w-[85%]',
          isUser
            ? 'bg-primary-container text-primary-foreground ml-auto'
            : 'bg-surface-2 text-foreground'
        )}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-headings:my-3 prose-code:bg-surface-3 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-surface-3 prose-pre:p-3">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== 工具调用卡片 ====================
function ToolInvocationCard({
  tool,
  isExpanded,
  onToggle,
}: {
  tool: any;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const getToolIcon = () => {
    if (tool.toolName?.includes('search')) return Search;
    if (tool.toolName?.includes('code') || tool.toolName?.includes('python'))
      return Code;
    return Code;
  };

  const Icon = getToolIcon();

  return (
    <div className="ml-11 bg-surface-3/30 border border-border/30 rounded-google overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-surface-3/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-foreground">
            {tool.toolName}
          </span>
          {tool.status === 'pending' && (
            <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="p-3 border-t border-border/30 bg-surface-2/50">
              <pre className="text-xs text-muted-foreground overflow-x-auto">
                {JSON.stringify(tool.args, null, 2)}
              </pre>
              {tool.result && (
                <div className="mt-2 pt-2 border-t border-border/20">
                  <div className="text-xs font-medium text-foreground mb-1">
                    结果:
                  </div>
                  <pre className="text-xs text-muted-foreground overflow-x-auto">
                    {JSON.stringify(tool.result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ==================== 空状态 ====================
function EmptyState() {
  const suggestions = [
    '解释最新的机器学习论文要点',
    '请帮我写一个 Python 脚本',
    '给我一个调研提纲',
    '帮我估算一下项目时间和人力',
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-12">
      <div className="w-16 h-16 bg-primary/10 rounded-google-lg flex items-center justify-center mb-4">
        <Bot className="w-8 h-8 text-primary" />
      </div>
      <h2 className="text-xl font-semibold text-foreground mb-2">开始对话</h2>
      <p className="text-sm text-muted-foreground mb-6 max-w-md">
        我可以帮你思考、搜索或写代码，输入你的需求即可开始。
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => {
              const inputEl = document.querySelector('textarea');
              if (inputEl) {
                (inputEl as HTMLTextAreaElement).value = suggestion;
                inputEl.dispatchEvent(new Event('input', { bubbles: true }));
                inputEl.focus();
              }
            }}
            className="text-left p-4 bg-surface-2 hover:bg-surface-3 rounded-google border border-border/30 transition-colors"
          >
            <p className="text-sm text-foreground">{suggestion}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
