/**
 * Studio Store 类型定义
 */

// ==================== 基础类型 ====================

export type StudioMode = 'general' | 'creative'

export type SessionStatus = 'idle' | 'active' | 'completed' | 'paused' | 'error'

export type CreativeStage = 
  | 'drafting'      // 草稿阶段
  | 'scripting'     // 脚本生成
  | 'visualizing'   // 分镜预览
  | 'rendering'     // 视频渲染
  | 'done'          // 完成

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

// ==================== 消息类型 ====================

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
  metadata?: Record<string, unknown>
}

export interface ToolCall {
  id: string
  name: string
  input: Record<string, unknown>
  output?: unknown
  status: 'pending' | 'running' | 'completed' | 'failed'
  startTime?: Date
  endTime?: Date
  cost?: number
}

// ==================== 会话类型 ====================

export interface BaseSession {
  id: string
  title: string
  mode: StudioMode
  status: SessionStatus
  createdAt: Date
  updatedAt: Date
  messages: Message[]
  backendId?: string  // 后端返回的会话 ID
}

export interface GeneralSession extends BaseSession {
  mode: 'general'
  goal?: string
  iteration: number
  maxIterations: number
  budgetUsd: number
  spentUsd: number
  toolCalls: ToolCall[]
}

export interface CreativeSession extends BaseSession {
  mode: 'creative'
  stage: CreativeStage
  brief?: string
  script?: string
  storyboard?: StoryboardPanel[]
  preview?: PreviewAsset
  renderedVideo?: string
  budgetUsd: number
  spentUsd: number
}

export type Session = GeneralSession | CreativeSession

// ==================== 创意模式相关类型 ====================

export interface StoryboardPanel {
  id: string
  index: number
  description: string
  visualCues: string
  estimatedDuration: number
  imageUrl?: string
}

export interface PreviewAsset {
  type: 'image' | 'video'
  url: string
  thumbnailUrl?: string
  duration?: number
}

// ==================== 资产类型 ====================

export interface Asset {
  id: string
  type: 'video' | 'image' | 'script' | 'audio'
  title: string
  url: string
  thumbnailUrl?: string
  sessionId: string
  createdAt: Date
  metadata?: Record<string, unknown>
}

// ==================== 配置类型 ====================

export interface GeneralConfig {
  model: string
  temperature: number
  topK: number
  topP: number
  maxTokens: number
  enableSearch: boolean
  enablePython: boolean
  enableMemory: boolean
  budgetLimit: number
}

export interface CreativeConfig {
  videoProvider: 'doubao' | 'runway' | 'pika' | 'runware'
  videoRatio: '16:9' | '9:16' | '1:1'
  videoDuration: 5 | 10 | 15 | 30
  videoQuality: 'draft' | 'standard' | 'high'
  stylePreset: string
  framesPerScene: number
  budgetLimit: number
  consistencyMode?: 'basic' | 'enhanced' | 'sequential'
}

// ==================== 布局类型 ====================

export type CanvasViewMode = 'default' | 'focus'

export interface LayoutConfig {
  sidebarWidth: number
  configPanelWidth: number
  sidebarCollapsed: boolean
  configPanelCollapsed: boolean
  sidebarOpen: boolean
  configPanelOpen: boolean
  canvasViewMode: CanvasViewMode
}

// ==================== Store 状态类型 ====================

export interface StudioState {
  // 模式
  mode: StudioMode
  
  // 会话管理
  sessions: Session[]
  currentSessionId: string | null
  
  // 资产
  assets: Asset[]
  
  // 配置
  generalConfig: GeneralConfig
  creativeConfig: CreativeConfig
  
  // 布局
  layout: LayoutConfig
  
  // 加载状态
  isLoading: boolean
  isStreaming: boolean
  error: string | null
}

// ==================== Store Actions 类型 ====================

export interface StudioActions {
  // 模式切换
  setMode: (mode: StudioMode) => void
  
  // 会话管理
  createSession: (mode: StudioMode, title?: string) => Session
  switchSession: (sessionId: string) => void
  deleteSession: (sessionId: string) => void
  updateSession: (sessionId: string, updates: Partial<Session>) => void
  setSessionBackendId: (sessionId: string, backendId: string) => void
  
  // 消息管理
  addMessage: (sessionId: string, message: Omit<Message, 'id' | 'timestamp'>) => void
  
  // 配置管理
  updateGeneralConfig: (config: Partial<GeneralConfig>) => void
  updateCreativeConfig: (config: Partial<CreativeConfig>) => void
  
  // 布局管理
  setSidebarWidth: (width: number) => void
  setConfigPanelWidth: (width: number) => void
  toggleSidebar: () => void
  toggleConfigPanel: () => void
  setCanvasViewMode: (mode: CanvasViewMode) => void
  
  // 流式状态
  isStreaming: boolean
  setStreaming: (streaming: boolean) => void
  
  // Creative 模式阶段
  setCreativeStage: (stage: CreativeStage) => void
  
  // 资产管理
  addAsset: (asset: Omit<Asset, 'id' | 'createdAt'>) => void
  removeAsset: (assetId: string) => void
  
  // 状态管理
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export type StudioStore = StudioState & StudioActions
