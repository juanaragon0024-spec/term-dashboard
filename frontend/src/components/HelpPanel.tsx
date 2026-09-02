export function HelpPanel() {
  const commands = [
    { cmd: '/theme <name>', desc: 'Cambiar tema (neon, dracula, monokai, catppuccin, gruvbox, tokyo)' },
    { cmd: '/effort <level>', desc: 'Cambiar esfuerzo (low, medium, high, max)' },
    { cmd: '/model <name>', desc: 'Cambiar modelo (claude, claude-opus, claude-haiku)' },
    { cmd: '/name <texto>', desc: 'Renombrar la pestana activa' },
    { cmd: '/workdir <ruta>', desc: 'Cambiar directorio de trabajo' },
    { cmd: '/new [nombre] [modelo]', desc: 'Nueva pestana (ej: /new MiChat claude-opus)' },
    { cmd: '/close', desc: 'Cerrar pestana activa' },
    { cmd: '/clear', desc: 'Limpiar chat' },
    { cmd: '/save', desc: 'Guardar configuracion' },
    { cmd: '/help', desc: 'Mostrar esta ayuda' },
    { cmd: '/apps', desc: 'Ir al panel de apps' },
    { cmd: '/tools', desc: 'Ir al panel de herramientas' },
    { cmd: '/settings', desc: 'Ir al panel de configuracion' },
    { cmd: '/about', desc: 'Info sobre Term' },
  ]

  const shortcuts = [
    { key: 'ctrl+t', desc: 'Nueva tab' },
    { key: 'ctrl+w', desc: 'Cerrar tab' },
    { key: 'ctrl+l', desc: 'Limpiar chat' },
    { key: 'ctrl+e', desc: 'Ciclar effort' },
    { key: 'escape', desc: 'Cancelar generacion' },
  ]

  return (
    <div className="help-panel">
      <div className="ascii-logo">
        <pre>{`████████╗ ███████╗ ██████╗  ███╗   ███╗
╚══██╔══╝ ██╔════╝ ██╔══██╗ ████╗ ████║
   ██║    █████╗   ██████╔╝ ██╔████╔██║
   ██║    ██╔══╝   ██╔══██╗ ██║╚██╔╝██║
   ██║    ███████╗ ██║  ██║ ██║ ╚═╝ ██║
   ╚═╝    ╚══════╝ ╚═╝  ╚═╝ ╚═╝     ╚═╝`}</pre>
      </div>

      <h2 className="panel-title">Que es Term?</h2>
      <p className="help-text">
        Dashboard multi-IA para terminal y web. Conecta con Claude Code via OAuth CLI.
        Puedes chatear, controlar tu Mac (abrir apps, cambiar musica, ajustar volumen), y mas.
      </p>

      <h3 className="help-subtitle">Comandos disponibles</h3>
      <div className="help-commands">
        {commands.map((c) => (
          <div key={c.cmd} className="help-cmd-row">
            <span className="help-cmd-name">{c.cmd}</span>
            <span className="help-cmd-desc">{c.desc}</span>
          </div>
        ))}
      </div>

      <h3 className="help-subtitle">Atajos de teclado (terminal)</h3>
      <div className="help-shortcuts">
        {shortcuts.map((s) => (
          <div key={s.key} className="shortcut">
            <span className="key">{s.key}</span> {s.desc}
          </div>
        ))}
      </div>

      <h3 className="help-subtitle">Control del sistema</h3>
      <p className="help-text">
        Pide cosas en el chat: "abre Safari", "pon la siguiente cancion en Spotify",
        "sube el volumen", "abre la terminal", "que cancion suena". Term usa osascript
        para controlar macOS directamente.
      </p>
    </div>
  )
}
