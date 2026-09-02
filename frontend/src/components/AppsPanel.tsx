const APPS = [
  { name: 'Visual Studio Code', cmd: 'code', category: 'Editor' },
  { name: 'Vim', cmd: 'vim', category: 'Editor' },
  { name: 'Neovim', cmd: 'nvim', category: 'Editor' },
  { name: 'Terminal', cmd: 'terminal', category: 'Terminal' },
  { name: 'htop', cmd: 'htop', category: 'Monitor' },
  { name: 'Python REPL', cmd: 'python3', category: 'Dev' },
  { name: 'Node.js REPL', cmd: 'node', category: 'Dev' },
  { name: 'Git', cmd: 'git', category: 'Dev' },
  { name: 'Docker', cmd: 'docker', category: 'Dev' },
  { name: 'Finder', cmd: 'open .', category: 'Files' },
]

export function AppsPanel() {
  const categories = APPS.reduce<Record<string, typeof APPS>>((acc, app) => {
    acc[app.category] = acc[app.category] || []
    acc[app.category].push(app)
    return acc
  }, {})

  return (
    <div className="apps-panel">
      <h2 className="panel-title">Aplicaciones</h2>
      <p className="panel-desc">Lanza aplicaciones directamente desde Term.</p>
      {Object.entries(categories).map(([cat, apps]) => (
        <div key={cat} className="apps-category">
          <h3 className="apps-category-title">{cat}</h3>
          <div className="apps-grid">
            {apps.map((app) => (
              <button key={app.cmd} className="app-card">
                <div className="app-name">{app.name}</div>
                <div className="app-cmd">{app.cmd}</div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
