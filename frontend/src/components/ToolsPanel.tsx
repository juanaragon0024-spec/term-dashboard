const TOOLS = [
  { name: 'Claude CLI', desc: 'OAuth activo', status: true },
  { name: 'Git', desc: 'Control de versiones', status: true },
  { name: 'Node.js', desc: 'Runtime JS', status: true },
  { name: 'Python', desc: 'Runtime Python', status: true },
  { name: 'Docker', desc: 'Contenedores', status: false },
]

export function ToolsPanel() {
  return (
    <div className="tools-panel">
      <h2 className="panel-title">Herramientas conectadas</h2>
      <p className="panel-desc">Estado de las herramientas disponibles para los modelos de IA.</p>
      <div className="tools-list">
        {TOOLS.map((tool) => (
          <div key={tool.name} className="tool-card">
            <div className="tool-info">
              <div className="tool-name">{tool.name}</div>
              <div className="tool-desc">{tool.desc}</div>
            </div>
            <div className={`tool-status ${tool.status ? 'active' : 'inactive'}`}>
              {tool.status ? 'Activo' : 'No encontrado'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
