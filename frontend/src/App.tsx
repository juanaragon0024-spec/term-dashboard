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
  /** Sesión de la CLI. Sin esto cada mensaje empezaría de cero, sin memoria. */
  sessionId?: string
  tokens?: number
  cost?: number
}

const EFFORT_LEVELS = ['low', 'medium', 'high', 'max'] as const
type Effort = (typeof EFFORT_LEVELS)[number]

function App() {
  const [tabs, setTabs] = useState<ChatTabData[]>([
    { id: 'tab-1', name: 'Chat', model: 'claude', modelName: 'Claude', messages: [], isLoading: false },
  ])
  const [activeTabId, setActiveTabId] = useState('tab-1')
  const [activePanel, setActivePanel] = useState<'chat' | 'settings' | 'apps' | 'tools' | 'help'>('chat')
  const [theme, setTheme] = useState<ThemeKey>(() => (localStorage.getItem('term-theme') as ThemeKey) || 'neon')
  const [effort, setEffort] = useState<Effort>(() => (localStorage.getItem('term-effort') as Effort) || 'high')
  const [workdir, setWorkdir] = useState(() => localStorage.getItem('term-workdir') || '')
  const [defaultModel, setDefaultModel] = useState('claude')
  const [contextTokens, setContextTokens] = useState(0)
  // La ventana real la dice el backend al terminar el turno.
  const [maxContext, setMaxContext] = useState(200000)
  const tabCounter = useRef(1)
  const abortRefs = useRef<Record<string, AbortController>>({})
  // Pestaña que se está renombrando ahora mismo, y el texto a medio escribir.
  const [editingTabId, setEditingTabId] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  // Marca de "esto se ha cancelado", para que el blur del desmontaje no
  // acabe guardando un nombre que el usuario ya había rechazado con Escape.
  const renameCancelled = useRef(false)

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
      name: name || `Chat ${tabs.length + 1}`,
      model: defaultModel,
      modelName: models[defaultModel] || 'Claude',
      messages: [],
      isLoading: false,
    }
    setTabs((prev) => [...prev, newTab])
    setActiveTabId(id)
    setActivePanel('chat')
  }, [defaultModel, tabs.length])

  const closeTab = useCallback((tabId: string) => {
    if (tabs.length <= 1) return
    abortRefs.current[tabId]?.abort()
    setTabs((prev) => {
      const next = prev.filter((t) => t.id !== tabId)
      // If only one tab left, rename it to "Chat"
      if (next.length === 1) {
        next[0] = { ...next[0], name: 'Chat' }
      }
      if (activeTabId === tabId && next.length > 0) setActiveTabId(next[0].id)
      return next
    })
  }, [tabs, activeTabId])

  const renameTab = useCallback((tabId: string, name: string) => {
    setTabs((prev) => prev.map((t) => t.id === tabId ? { ...t, name } : t))
  }, [])

  const startRename = useCallback((tabId: string, current: string) => {
    setEditingTabId(tabId)
    setDraftName(current)
  }, [])

  const commitRename = useCallback(() => {
    if (renameCancelled.current) {
      renameCancelled.current = false
      setEditingTabId(null)
      return
    }
    if (editingTabId) {
      const name = draftName.trim()
      // Un nombre vacío dejaría la pestaña sin etiqueta: se descarta.
      if (name) renameTab(editingTabId, name)
    }
    setEditingTabId(null)
  }, [editingTabId, draftName, renameTab])

  const cancelRename = useCallback(() => {
    renameCancelled.current = true
    setEditingTabId(null)
  }, [])

  const clearTab = useCallback((tabId: string) => {
    // Se olvida también la sesión: si no, la IA seguiría recordando una
    // conversación que el usuario ya no ve.
    setTabs((prev) => prev.map((t) =>
      t.id === tabId
        ? { ...t, messages: [], sessionId: undefined, tokens: 0, cost: 0 }
        : t))
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

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          workdir: workdir || undefined,
          model: tab?.model,
          effort,
          // A partir del segundo mensaje se continúa la conversación en curso.
          sessionId: tab?.sessionId,
          resume: Boolean(tab?.sessionId),
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

            } else if (data.type === 'session') {
              // El id llega al principio; se guarda para el turno siguiente.
              setTabs((prev) => prev.map((t) =>
                t.id === tabId ? { ...t, sessionId: data.sessionId } : t))

            } else if (data.type === 'tool') {
              setTabs((prev) => prev.map((t) =>
                t.id === tabId
                  ? { ...t, messages: t.messages.map((m) => m.id === assistantId
                      ? { ...m, content: m.content + `\n\n\`${data.name}\`\n\n` } : m) }
                  : t
              ))

            } else if (data.type === 'usage') {
              // Tokens y coste reales, que antes se estimaban por palabras.
              setContextTokens(data.tokens || 0)
              setTabs((prev) => prev.map((t) =>
                t.id === tabId
                  ? { ...t, tokens: data.tokens || 0, cost: data.cost || 0 }
                  : t))
              if (data.contextWindow) setMaxContext(data.contextWindow)

            } else if (data.type === 'error') {
              setTabs((prev) => prev.map((t) =>
                t.id === tabId
                  ? { ...t, messages: t.messages.map((m) => m.id === assistantId
                      ? { ...m, content: (m.content ? m.content + '\n\n' : '') + `Error: ${data.content}` } : m) }
                  : t
              ))
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
              {editingTabId === tab.id ? (
                <input
                  className="tab-rename"
                  value={draftName}
                  autoFocus
                  spellCheck={false}
                  onChange={(e) => setDraftName(e.target.value)}
                  onBlur={commitRename}
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); commitRename() }
                    if (e.key === 'Escape') { e.preventDefault(); cancelRename() }
                  }}
                />
              ) : (
                <span
                  className="tab-name"
                  title="Doble clic para renombrar"
                  onDoubleClick={(e) => { e.stopPropagation(); startRename(tab.id, tab.name) }}
                >
                  {tab.name}
                </span>
              )}
              {tabs.length > 1 && editingTabId !== tab.id && (
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
          {Boolean(activeTab?.cost) && (
            <span className="status-item cost">
              Coste: ${activeTab!.cost!.toFixed(4)}
            </span>
          )}
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
