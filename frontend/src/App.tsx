import { useState, useRef, useEffect, useCallback } from 'react'
import './App.css'
import { ChatPanel } from './components/ChatPanel'
import { Sidebar } from './components/Sidebar'
import { SettingsPanel } from './components/SettingsPanel'
import { AppsPanel } from './components/AppsPanel'
import { ToolsPanel } from './components/ToolsPanel'
import { HelpPanel } from './components/HelpPanel'
import { themes, type ThemeKey } from './themes'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface ChatTabData {
  id: string
  name: string
  model: string
  modelName: string
  messages: Message[]
  isLoading: boolean
}

const EFFORT_LEVELS = ['low', 'medium', 'high', 'max'] as const
type Effort = (typeof EFFORT_LEVELS)[number]

function App() {
  const [tabs, setTabs] = useState<ChatTabData[]>([
    { id: 'tab-1', name: 'Chat 1', model: 'claude', modelName: 'Claude', messages: [], isLoading: false },
  ])
  const [activeTabId, setActiveTabId] = useState('tab-1')
  const [activePanel, setActivePanel] = useState<'chat' | 'settings' | 'apps' | 'tools' | 'help'>('chat')
  const [theme, setTheme] = useState<ThemeKey>(() => (localStorage.getItem('term-theme') as ThemeKey) || 'neon')
  const [effort, setEffort] = useState<Effort>(() => (localStorage.getItem('term-effort') as Effort) || 'high')
  const [workdir, setWorkdir] = useState(() => localStorage.getItem('term-workdir') || '')
  const [defaultModel, setDefaultModel] = useState('claude')
  const [contextTokens, setContextTokens] = useState(0)
  const maxContext = 200000
  const tabCounter = useRef(1)
  const abortRefs = useRef<Record<string, AbortController>>({})

  useEffect(() => {
    localStorage.setItem('term-theme', theme)
    const t = themes[theme]
    const root = document.documentElement
    Object.entries(t.vars).forEach(([k, v]) => root.style.setProperty(k, v))
  }, [theme])

  useEffect(() => { localStorage.setItem('term-effort', effort) }, [effort])
  useEffect(() => { if (workdir) localStorage.setItem('term-workdir', workdir) }, [workdir])

  const activeTab = tabs.find((t) => t.id === activeTabId)

  const addTab = useCallback((name?: string) => {
    tabCounter.current++
    const models: Record<string, string> = { claude: 'Claude', 'claude-opus': 'Claude Opus', 'claude-haiku': 'Claude Haiku' }
    const id = `tab-${tabCounter.current}`
    const newTab: ChatTabData = {
      id,
      name: name || `Chat ${tabCounter.current}`,
      model: defaultModel,
      modelName: models[defaultModel] || 'Claude',
      messages: [],
      isLoading: false,
    }
    setTabs((prev) => [...prev, newTab])
    setActiveTabId(id)
    setActivePanel('chat')
  }, [defaultModel])

  const closeTab = useCallback((tabId: string) => {
    if (tabs.length <= 1) return
    abortRefs.current[tabId]?.abort()
    setTabs((prev) => {
      const next = prev.filter((t) => t.id !== tabId)
      if (activeTabId === tabId && next.length > 0) setActiveTabId(next[0].id)
      return next
    })
  }, [tabs, activeTabId])

  const renameTab = useCallback((tabId: string, name: string) => {
    setTabs((prev) => prev.map((t) => t.id === tabId ? { ...t, name } : t))
  }, [])

  const clearTab = useCallback((tabId: string) => {
    setTabs((prev) => prev.map((t) => t.id === tabId ? { ...t, messages: [] } : t))
    setContextTokens(0)
  }, [])

  const cycleEffort = useCallback(() => {
    setEffort((prev) => {
      const idx = EFFORT_LEVELS.indexOf(prev)
      return EFFORT_LEVELS[(idx + 1) % EFFORT_LEVELS.length]
    })
  }, [])

  const sendMessage = useCallback(async (text: string, tabId: string) => {
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text }
    const assistantId = crypto.randomUUID()
    const assistantMsg: Message = { id: assistantId, role: 'assistant', content: '' }

    setTabs((prev) => prev.map((t) =>
      t.id === tabId ? { ...t, messages: [...t.messages, userMsg, assistantMsg], isLoading: true } : t
    ))

    try {
      const controller = new AbortController()
      abortRefs.current[tabId] = controller
      const tab = tabs.find((t) => t.id === tabId)

      const res = await fetch('http://localhost:3001/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          workdir: workdir || undefined,
          model: tab?.model,
          effort,
        }),
        signal: controller.signal,
      })

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No reader')

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'chunk') {
              setTabs((prev) => prev.map((t) =>
                t.id === tabId
                  ? { ...t, messages: t.messages.map((m) => m.id === assistantId ? { ...m, content: m.content + data.content } : m) }
                  : t
              ))
              if (data.tokens) setContextTokens(data.tokens)
            }
          } catch {}
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setTabs((prev) => prev.map((t) =>
          t.id === tabId
            ? { ...t, messages: t.messages.map((m) => m.id === assistantId ? { ...m, content: 'Error de conexion con el backend.' } : m) }
            : t
        ))
      }
    } finally {
      delete abortRefs.current[tabId]
      setTabs((prev) => prev.map((t) => (t.id === tabId ? { ...t, isLoading: false } : t)))
    }
  }, [workdir, effort, tabs])

  const stopGeneration = useCallback((tabId: string) => {
    abortRefs.current[tabId]?.abort()
    setTabs((prev) => prev.map((t) => (t.id === tabId ? { ...t, isLoading: false } : t)))
  }, [])

  const contextPct = Math.min(100, Math.round(contextTokens / maxContext * 100))

  const models: Record<string, string> = { claude: 'Claude', 'claude-opus': 'Claude Opus', 'claude-haiku': 'Claude Haiku' }

  return (
    <div className="app">
      <Sidebar activePanel={activePanel} onPanelChange={setActivePanel} />
      <div className="main-area">
        {/* Tab bar */}
        <div className="tab-bar">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={`tab ${tab.id === activeTabId ? 'active' : ''}`}
              onClick={() => { setActiveTabId(tab.id); setActivePanel('chat') }}
            >
              <span className="tab-name">{tab.name}</span>
              {tabs.length > 1 && (
                <button className="tab-close" onClick={(e) => { e.stopPropagation(); closeTab(tab.id) }}>x</button>
              )}
            </div>
          ))}
          <button className="tab-add" onClick={() => addTab()}>+</button>
        </div>

        {/* Panels */}
        {activePanel === 'chat' && activeTab && (
          <ChatPanel
            key={activeTab.id}
            tab={activeTab}
            onSend={(text) => sendMessage(text, activeTab.id)}
            onStop={() => stopGeneration(activeTab.id)}
            onClear={() => clearTab(activeTab.id)}
            theme={theme}
          />
        )}
        {activePanel === 'settings' && (
          <SettingsPanel
            theme={theme} onThemeChange={setTheme}
            workdir={workdir} onWorkdirChange={setWorkdir}
            defaultModel={defaultModel} onDefaultModelChange={setDefaultModel}
            effort={effort} onEffortChange={setEffort}
          />
        )}
        {activePanel === 'apps' && <AppsPanel />}
        {activePanel === 'tools' && <ToolsPanel />}
        {activePanel === 'help' && <HelpPanel />}

        {/* Status bar */}
        <div className="status-bar">
          <span className="status-item effort" onClick={cycleEffort}>
            Effort: {effort}
          </span>
          <span className="status-item context">
            Contexto: <span className="context-bar">{'█'.repeat(Math.round(contextPct / 100 * 15))}{'░'.repeat(15 - Math.round(contextPct / 100 * 15))}</span> {contextPct}% ({contextTokens.toLocaleString()}/{maxContext.toLocaleString()})
          </span>
          <span className="status-item model">
            {models[activeTab?.model || 'claude'] || 'Claude'}
          </span>
          {workdir && <span className="status-item workdir">{workdir.length > 30 ? '...' + workdir.slice(-27) : workdir}</span>}
        </div>
      </div>
    </div>
  )
}

export default App
