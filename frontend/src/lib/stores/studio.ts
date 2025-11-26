/**
 * Studio Store - Zustand 状态管理
 * 管理整个工作区的状态，包括会话、配置、布局等
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { generateId } from '@/lib/utils'
import type {
  StudioStore,
  StudioState,
  StudioMode,
  Session,
  GeneralSession,
  CreativeSession,
  Message,
  Asset,
  GeneralConfig,
  CreativeConfig,
  CanvasViewMode,
  CreativeStage,
} from './types'

// ==================== 默认值 ====================

const defaultGeneralConfig: GeneralConfig = {
  model: 'openai/gpt-4o',
  temperature: 0.7,
  topK: 40,
  topP: 0.95,
  maxTokens: 2048,
  enableSearch: true,
  enablePython: true,
  enableMemory: true,
  budgetLimit: 5.0,
}

const defaultCreativeConfig: CreativeConfig = {
  videoProvider: 'doubao',
  videoRatio: '16:9',
  videoDuration: 15,
  videoQuality: 'standard',
  stylePreset: 'cinematic',
  framesPerScene: 4,
  budgetLimit: 50.0,
  consistencyMode: 'enhanced',
}

const defaultLayout = {
  sidebarWidth: 280,
  configPanelWidth: 320,
  sidebarCollapsed: false,
  configPanelCollapsed: false,
  sidebarOpen: true,
  configPanelOpen: true,
  canvasViewMode: 'default' as const,
}

const initialState: StudioState = {
  mode: 'general',
  sessions: [],
  currentSessionId: null,
  assets: [],
  generalConfig: defaultGeneralConfig,
  creativeConfig: defaultCreativeConfig,
  layout: defaultLayout,
  isLoading: false,
  isStreaming: false,
  error: null,
}

// ==================== 辅助函数 ====================

function createGeneralSession(): GeneralSession {
  const id = generateId()
  return {
    id,
    title: '新对话',
    mode: 'general',
    status: 'idle',
    createdAt: new Date(),
    updatedAt: new Date(),
    messages: [],
    iteration: 0,
    maxIterations: 10,
    budgetUsd: defaultGeneralConfig.budgetLimit,
    spentUsd: 0,
    toolCalls: [],
  }
}

function createCreativeSession(): CreativeSession {
  const id = generateId()
  return {
    id,
    title: '新项目',
    mode: 'creative',
    status: 'idle',
    createdAt: new Date(),
    updatedAt: new Date(),
    messages: [],
    stage: 'drafting',
    budgetUsd: defaultCreativeConfig.budgetLimit,
    spentUsd: 0,
  }
}

// ==================== Store 创建 ====================

export const useStudioStore = create<StudioStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      // ========== 模式切换 ==========
      setMode: (mode: StudioMode) => {
        const state = get()
        
        // 查找该模式下的会话
        const sessionsInMode = state.sessions.filter(s => s.mode === mode)
        
        if (sessionsInMode.length > 0) {
          // 切换到该模式下最新的会话
          set({ 
            mode,
            currentSessionId: sessionsInMode[0].id,
          })
        } else {
          // 该模式下没有会话，创建新会话
          const session = mode === 'general' 
            ? createGeneralSession() 
            : createCreativeSession()
          
          set((state) => ({
            mode,
            sessions: [session, ...state.sessions],
            currentSessionId: session.id,
          }))
        }
      },

      // ========== 会话管理 ==========
      createSession: (mode: StudioMode, title?: string): Session => {
        const session = mode === 'general' 
          ? createGeneralSession() 
          : createCreativeSession()
        
        if (title) {
          session.title = title
        }
        
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: session.id,
        }))
        
        return session
      },

      switchSession: (sessionId: string) => {
        const session = get().sessions.find(s => s.id === sessionId)
        if (session) {
          set({ 
            currentSessionId: sessionId,
            mode: session.mode,
          })
        }
      },

      deleteSession: (sessionId: string) => {
        set((state) => {
          const newSessions = state.sessions.filter(s => s.id !== sessionId)
          const newCurrentId = state.currentSessionId === sessionId
            ? (newSessions.length > 0 ? newSessions[0].id : null)
            : state.currentSessionId
          
          return {
            sessions: newSessions,
            currentSessionId: newCurrentId,
          }
        })
      },

      updateSession: (sessionId: string, updates: Partial<Session>) => {
        set((state) => ({
          sessions: state.sessions.map(s => 
            s.id === sessionId 
              ? { ...s, ...updates, updatedAt: new Date() } as Session
              : s
          ),
        }))
      },

      setSessionBackendId: (sessionId: string, backendId: string) => {
        set((state) => ({
          sessions: state.sessions.map(s => 
            s.id === sessionId 
              ? { ...s, backendId, updatedAt: new Date() } as Session
              : s
          ),
        }))
      },

      // ========== 消息管理 ==========
      addMessage: (sessionId: string, message: Omit<Message, 'id' | 'timestamp'>) => {
        const newMessage: Message = {
          ...message,
          id: generateId(),
          timestamp: new Date(),
        }
        
        set((state) => ({
          sessions: state.sessions.map(s => 
            s.id === sessionId
              ? { 
                  ...s, 
                  messages: [...s.messages, newMessage],
                  updatedAt: new Date(),
                  // 更新标题为第一条用户消息
                  title: s.messages.length === 0 && message.role === 'user'
                    ? message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '')
                    : s.title,
                } as Session
              : s
          ),
        }))
      },

      // ========== 配置管理 ==========
      updateGeneralConfig: (config: Partial<GeneralConfig>) => {
        set((state) => ({
          generalConfig: { ...state.generalConfig, ...config },
        }))
      },

      updateCreativeConfig: (config: Partial<CreativeConfig>) => {
        set((state) => ({
          creativeConfig: { ...state.creativeConfig, ...config },
        }))
      },

      // ========== 布局管理 ==========
      setSidebarWidth: (width: number) => {
        set((state) => ({
          layout: { ...state.layout, sidebarWidth: width },
        }))
      },

      setConfigPanelWidth: (width: number) => {
        set((state) => ({
          layout: { ...state.layout, configPanelWidth: width },
        }))
      },

      toggleSidebar: () => {
        set((state) => ({
          layout: { 
            ...state.layout, 
            sidebarCollapsed: !state.layout.sidebarCollapsed,
            sidebarOpen: !state.layout.sidebarOpen,
          },
        }))
      },

      toggleConfigPanel: () => {
        set((state) => ({
          layout: { 
            ...state.layout, 
            configPanelCollapsed: !state.layout.configPanelCollapsed,
            configPanelOpen: !state.layout.configPanelOpen,
          },
        }))
      },

      setCanvasViewMode: (mode: CanvasViewMode) => {
        set((state) => ({
          layout: { ...state.layout, canvasViewMode: mode },
        }))
      },

      // ========== 资产管理 ==========
      addAsset: (asset: Omit<Asset, 'id' | 'createdAt'>) => {
        const newAsset: Asset = {
          ...asset,
          id: generateId(),
          createdAt: new Date(),
        }
        
        set((state) => ({
          assets: [newAsset, ...state.assets],
        }))
      },

      removeAsset: (assetId: string) => {
        set((state) => ({
          assets: state.assets.filter(a => a.id !== assetId),
        }))
      },

      // ========== 状态管理 ==========
      setLoading: (loading: boolean) => {
        set({ isLoading: loading })
      },

      setStreaming: (streaming: boolean) => {
        set({ isStreaming: streaming })
      },

      setCreativeStage: (stage: CreativeStage) => {
        const currentSessionId = get().currentSessionId
        if (currentSessionId) {
          set((state) => ({
            sessions: state.sessions.map(s => 
              s.id === currentSessionId && s.mode === 'creative'
                ? { ...s, stage, updatedAt: new Date() } as Session
                : s
            ),
          }))
        }
      },

      setError: (error: string | null) => {
        set({ error })
      },

      reset: () => {
        set(initialState)
      },
    }),
    {
      name: 'nexgen-studio-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        mode: state.mode,
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        assets: state.assets,
        generalConfig: state.generalConfig,
        creativeConfig: state.creativeConfig,
        layout: state.layout,
      }),
    }
  )
)

// ==================== Selectors ====================

/**
 * 获取当前会话
 */
export const selectCurrentSession = (state: StudioState): Session | null => {
  if (!state.currentSessionId) return null
  return state.sessions.find(s => s.id === state.currentSessionId) || null
}

/**
 * 按模式筛选会话
 */
export const selectSessionsByMode = (state: StudioState, mode: StudioMode): Session[] => {
  return state.sessions.filter(s => s.mode === mode)
}

/**
 * 获取当前模式的配置
 */
export const selectCurrentConfig = (state: StudioState) => {
  return state.mode === 'general' ? state.generalConfig : state.creativeConfig
}
