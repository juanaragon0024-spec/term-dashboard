import type { ThemeKey } from '../themes'

interface SidebarProps {
  activePanel: 'chat' | 'settings' | 'apps' | 'tools'
  onPanelChange: (panel: 'chat' | 'settings' | 'apps' | 'tools') => void
  effort: string
  onCycleEffort: () => void
  theme: ThemeKey
}

export function Sidebar({ activePanel, onPanelChange, effort, onCycleEffort, theme }: SidebarProps) {
  const panels = [
    { key: 'chat' as const, label: 'Chat' },
    { key: 'settings' as const, label: 'Settings' },
    { key: 'apps' as const, label: 'Apps' },
    { key: 'tools' as const, label: 'Tools' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-title">TERM</div>
      </div>

      <nav className="sidebar-nav">
        {panels.map((p) => (
          <button
            key={p.key}
            className={`sidebar-nav-btn ${activePanel === p.key ? 'active' : ''}`}
            onClick={() => onPanelChange(p.key)}
          >
            {p.label}
          </button>
        ))}
      </nav>

      <div style={{ flex: 1 }} />

      <div className="sidebar-footer">
        <button className="sidebar-effort-btn" onClick={onCycleEffort}>
          Effort: {effort}
        </button>
        <div className="sidebar-status">
          <span className="status-dot" />
          OAuth CLI
        </div>
      </div>
    </aside>
  )
}
