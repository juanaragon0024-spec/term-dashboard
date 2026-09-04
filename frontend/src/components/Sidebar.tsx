export type PanelKey = 'chat' | 'settings' | 'apps' | 'tools' | 'help'

interface SidebarProps {
  activePanel: PanelKey
  onPanelChange: (panel: PanelKey) => void
  /** Estado de la conexión con el backend, para el pie. */
  online?: boolean
  tabs?: number
}

const PANELS: { key: PanelKey; label: string; hint: string }[] = [
  { key: 'chat', label: 'Chat', hint: 'La conversación' },
  { key: 'settings', label: 'Ajustes', hint: 'Modelo, tema y esfuerzo' },
  { key: 'apps', label: 'Archivos', hint: 'Tu directorio de trabajo' },
  { key: 'tools', label: 'Herramientas', hint: 'Lo que hay instalado' },
  { key: 'help', label: 'Ayuda', hint: 'Comandos y atajos' },
]

export function Sidebar({ activePanel, onPanelChange, online = true, tabs = 1 }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-title">TERM</div>
        <div className="sidebar-sub">en el navegador</div>
      </div>

      <nav className="sidebar-nav">
        {PANELS.map((p) => (
          <button
            key={p.key}
            className={`sidebar-nav-btn ${activePanel === p.key ? 'active' : ''}`}
            onClick={() => onPanelChange(p.key)}
            title={p.hint}
          >
            <span className="sidebar-nav-label">{p.label}</span>
            {p.key === 'chat' && tabs > 1 && (
              <span className="sidebar-badge">{tabs}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-spacer" />

      <div className="sidebar-footer">
        <div className={`sidebar-status ${online ? '' : 'offline'}`}>
          <span className="status-dot" />
          {online ? 'Conectado' : 'Sin backend'}
        </div>
      </div>
    </aside>
  )
}
