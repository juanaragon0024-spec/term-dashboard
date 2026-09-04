import { useMemo, useState } from 'react'
import { COMMAND_GROUPS, SHORTCUTS } from '../commands.generated'

const LOGO = `████████╗ ███████╗ ██████╗  ███╗   ███╗
╚══██╔══╝ ██╔════╝ ██╔══██╗ ████╗ ████║
   ██║    █████╗   ██████╔╝ ██╔████╔██║
   ██║    ██╔══╝   ██╔══██╗ ██║╚██╔╝██║
   ██║    ███████╗ ██║  ██║ ██║ ╚═╝ ██║
   ╚═╝    ╚══════╝ ╚═╝  ╚═╝ ╚═╝     ╚═╝`

const EJEMPLOS = [
  'crea una carpeta notas y mete dentro un README',
  'busca dónde está el archivo de configuración',
  'qué archivos de este proyecto mencionan ChatSession',
  'explícame qué hace esta función',
]

type Filtro = 'todos' | 'web'

export function HelpPanel() {
  const [busqueda, setBusqueda] = useState('')
  const [filtro, setFiltro] = useState<Filtro>('todos')

  const grupos = useMemo(() => {
    const aguja = busqueda.trim().toLowerCase()
    return COMMAND_GROUPS.map((g) => ({
      ...g,
      commands: g.commands.filter(
        (c) =>
          (filtro === 'todos' || c.web) &&
          (!aguja ||
            c.cmd.toLowerCase().includes(aguja) ||
            c.desc.toLowerCase().includes(aguja)),
      ),
    })).filter((g) => g.commands.length > 0)
  }, [busqueda, filtro])

  const total = grupos.reduce((n, g) => n + g.commands.length, 0)

  return (
    <div className="help-panel">
      <div className="ascii-logo">
        <pre>{LOGO}</pre>
      </div>

      <p className="help-lead">
        Una terminal con IA que además actúa. Aquí, en el navegador, tienes el
        chat y los ajustes; la versión de terminal añade git, procesos en
        segundo plano, MCP y control del sistema.
      </p>

      <section className="help-section">
        <h3 className="help-subtitle">Qué le puedes pedir</h3>
        <ul className="help-examples">
          {EJEMPLOS.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      </section>

      <section className="help-section">
        <div className="help-toolbar">
          <h3 className="help-subtitle">Comandos</h3>
          <div className="help-filters">
            <button
              className={`chip ${filtro === 'todos' ? 'active' : ''}`}
              onClick={() => setFiltro('todos')}
            >
              Todos
            </button>
            <button
              className={`chip ${filtro === 'web' ? 'active' : ''}`}
              onClick={() => setFiltro('web')}
            >
              Solo en el navegador
            </button>
          </div>
        </div>

        <input
          className="help-search"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Filtrar comandos…"
          spellCheck={false}
        />

        {total === 0 && (
          <p className="help-empty">Ningún comando coincide con «{busqueda}».</p>
        )}

        {grupos.map((g) => (
          <div key={g.key} className="help-group">
            <h4 className="help-group-title">{g.title}</h4>
            <div className="help-commands">
              {g.commands.map((c) => (
                <div key={c.cmd} className={`help-cmd-row ${c.web ? '' : 'solo-terminal'}`}>
                  <code className="help-cmd-name">{c.cmd}</code>
                  <span className="help-cmd-desc">{c.desc}</span>
                  {!c.web && <span className="help-badge" title="Solo en la terminal">term</span>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="help-section">
        <h3 className="help-subtitle">Atajos</h3>
        <div className="help-shortcuts">
          {Object.entries(SHORTCUTS).map(([k, d]) => (
            <div key={k} className="shortcut">
              <kbd>{k}</kbd>
              <span>{d}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
