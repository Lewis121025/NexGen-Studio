/**
 * General Canvas - 通用对话界面
 * 真实流式聊天 + 工具调用卡片
 */

'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Loader2,
  User,
  Bot,
  Search,
  Code,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useEffect, useRef, useState, type JSX } from 'react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useStudioStore, selectCurrentSession } from '@/lib/stores/studio';
import type { Message, ToolInvocation, Session } from '@/lib/stores/types';
import { cn } from '@/lib/utils';

type SSEStatus = 'thinking' | 'processing' | 'completed' | 'error';

interface BackendSessionPayload {
  summary?: string;
  messages?: string[];
  tool_calls?: ToolInvocation[];
}

interface SSEPayload {
  status?: SSEStatus;
  message?: unknown;
  session?: unknown;
}

const isString = (v: unknown): v is string => typeof v === 'string';
const isStringArray = (v: unknown): v is string[] => Array.isArray(v) && v.every(isString);
const isToolInvocationArray = (v: unknown): v is ToolInvocation[] =>
  Array.isArray(v) &&
  v.every(
    (item) =>
      item &&
      typeof item === 'object' &&
      'toolName' in item &&
      'status' in item,
  );

function parseSessionPayload(value: unknown): BackendSessionPayload | null {
  if (!value || typeof value !== 'object') return null;
  
  // 后端返回格式: { session: { session: GeneralSession } } 
  // 需要解析嵌套的 session 对象
  let session = value as Record<string, unknown>;
  
  // 处理双重嵌套: response.session.session
  if ('session' in session && session.session && typeof session.session === 'object') {
    session = session.session as Record<string, unknown>;
  }
  
  const parsed: BackendSessionPayload = {};
  if (isString(session.summary)) parsed.summary = session.summary;
  if (isStringArray(session.messages)) parsed.messages = session.messages;
  
  // 解析工具调用记录 - 后端格式与前端格式不同
  if (Array.isArray(session.tool_calls)) {
    parsed.tool_calls = session.tool_calls.map((tc: Record<string, unknown>) => ({
      toolName: isString(tc.tool) ? tc.tool : 'unknown',
      status: 'completed' as const,
      args: tc.arguments,
      result: tc.output,
    }));
  }
  
  return parsed;
}

// 提取 AI 回复内容
function extractAssistantMessage(sessionData: BackendSessionPayload | null): string {
  if (!sessionData) return '处理完成';
  
  // 优先使用 summary
  if (sessionData.summary) {
    return sessionData.summary;
  }
  
  // 从 messages 中提取最后一条 Assistant 回复
  if (sessionData.messages && sessionData.messages.length > 0) {
    const assistantMessages = sessionData.messages.filter(
      (msg) => msg.startsWith('Assistant:')
    );
    if (assistantMessages.length > 0) {
      return assistantMessages[assistantMessages.length - 1].replace('Assistant: ', '');
    }
    
    // 回退：找最后一条非用户消息
    const aiMessages = sessionData.messages.filter(
      (msg) => !msg.startsWith('User:') && !msg.startsWith('Goal registered:')
    );
    if (aiMessages.length > 0) {
      return aiMessages[aiMessages.length - 1];
    }
  }
  
  return '处理完成';
}

function uuid(): string {
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function GeneralCanvas(): JSX.Element {
  const createSession = useStudioStore((state) => state.createSession);
  const setSessionBackendId = useStudioStore(
    (state) => state.setSessionBackendId
  );
  const addMessage = useStudioStore((state) => state.addMessage);
  const isStreaming = useStudioStore((state) => state.isStreaming);
  const setStreaming = useStudioStore((state) => state.setStreaming);
  const currentSession = useStudioStore(selectCurrentSession);

  const [input, setInput] = useState('');
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [statusText, setStatusText] = useState<string>('AI 正在思考...');
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [currentSession?.messages]);

  useEffect(
    (): (() => void) =>
      () => {
        if (abortRef.current) abortRef.current.abort();
      },
    []
  );

  const ensureSession = (): Session => {
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
    const data: unknown = await res.json();
    const backendId =
      data &&
      typeof data === 'object' &&
      'session' in data &&
      (data as { session?: unknown }).session &&
      typeof (data as { session?: { id?: unknown } }).session === 'object'
        ? (data as { session?: { id?: unknown } }).session?.id
        : undefined;
    if (!isString(backendId)) throw new Error('未获取到会话 ID');
    setSessionBackendId(sessionId, backendId);
    return backendId;
  };

  const handleSSEEvent = (payload: unknown, sessionId: string): void => {
    if (!payload || typeof payload !== 'object') return;
    const data = payload as SSEPayload;
    const status = data.status;

    if (status === 'thinking') {
      setStatusText('AI 正在思考...');
      return;
    }
    if (status === 'processing') {
      setStatusText('AI 正在调用工具...');
      return;
    }
    if (status === 'completed') {
      const sessionData = parseSessionPayload(data.session);
      const assistantText = extractAssistantMessage(sessionData);
      
      addMessage(sessionId, {
        id: uuid(),
        role: 'assistant',
        content: assistantText,
        timestamp: new Date(),
        toolInvocations: sessionData?.tool_calls,
      });
      setStreaming(false);
      setStatusText('');
      return;
    }
    if (status === 'error') {
      const message =
        typeof data.message === 'string' && data.message
          ? data.message
          : '处理失败';
      addMessage(sessionId, {
        id: uuid(),
        role: 'assistant',
        content: message,
        timestamp: new Date(),
      });
      setStreaming(false);
      setStatusText('');
    }
  };
  const handleSend = async (): Promise<void> => {
    if (!input.trim() || isStreaming) return;

    const session = ensureSession();
    const text = input.trim();
    setInput('');
    setStreaming(true);
    setStatusText('AI 正在思考...');

    const userMessage: Message = {
      id: uuid(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    addMessage(session.id, userMessage);

    try {
      const backendId = await ensureBackendSession(text, session.id);
      const form = new FormData();
      form.append('prompt', text);

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

      const flushEvents = (chunk: string): void => {
        buffer += chunk;
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);
          if (!raw.startsWith('data:')) continue;
          try {
            const payload: unknown = JSON.parse(raw.replace(/^data:\s*/, ''));
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
    } catch (e: unknown) {
      console.error(e);
      const message = e instanceof Error && e.message ? e.message : '发送失败';
      addMessage(session.id, {
        id: uuid(),
        role: 'assistant',
        content: message,
        timestamp: new Date(),
      });
      setStreaming(false);
      setStatusText('');
    } finally {
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const toggleToolExpansion = (toolId: string): void => {
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

  return (
    <div className="h-full flex flex-col bg-surface-1">
      {/* 信息列表 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {!currentSession || currentSession.messages.length === 0 ? (
            <EmptyState onSuggestionClick={(text) => setInput(text)} />
          ) : (
            <AnimatePresence mode="popLayout">
              {currentSession.messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.2 }}
                >
                  <MessageBubble message={message} />

                  {/* Tool Invocations */}
                  {message.toolInvocations &&
                    message.toolInvocations.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {message.toolInvocations.map((tool, toolIndex) => (
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
          <div className="relative">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="请输入你的问题、任务或代码... (Shift + Enter 换行)"
              className="min-h-[80px] max-h-[200px] pr-12 rounded-google-lg bg-surface-1 border-border/50 focus-visible:ring-primary resize-none"
              disabled={isStreaming}
            />
            <Button
              size="icon"
              onClick={() => { void handleSend(); }}
              disabled={!input.trim() || isStreaming}
              className="absolute right-2 bottom-2 rounded-full bg-primary hover:bg-primary/90"
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>

          <div className="mt-2 text-xs text-muted-foreground text-center">
            Lewis AI 会实时推理与调用工具，结果将流式返回
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== 信息气泡 ====================
function MessageBubble({ message }: { message: Message }): JSX.Element {
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
        <div className="prose prose-sm dark:prose-invert max-w-none">
          {message.content}
        </div>
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
  tool: ToolInvocation;
  isExpanded: boolean;
  onToggle: () => void;
}): JSX.Element {
  const getToolIcon = (): typeof Search => {
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
function EmptyState({ onSuggestionClick }: { onSuggestionClick: (text: string) => void }): JSX.Element {
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
            onClick={() => onSuggestionClick(suggestion)}
            className="text-left p-4 bg-surface-2 hover:bg-surface-3 rounded-google border border-border/30 transition-colors cursor-pointer"
          >
            <p className="text-sm text-foreground">{suggestion}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
