export function HelpPanel() {
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
        Un dashboard multi-IA para terminal y web. Conecta con Claude Code via OAuth CLI.
        Puedes chatear, controlar tu Mac (abrir apps, cambiar musica, ajustar volumen), y mas.
      </p>

      <h3 className="help-subtitle">Control del sistema</h3>
      <p className="help-text">
        Pide cosas en el chat como: "abre Safari", "pon la siguiente cancion en Spotify",
        "sube el volumen", "abre la terminal". Term usa osascript para controlar macOS.
      </p>

      <h3 className="help-subtitle">Atajos</h3>
      <div className="help-shortcuts">
        <div className="shortcut"><span className="key">+</span> Nueva tab</div>
        <div className="shortcut"><span className="key">x</span> Cerrar tab</div>
        <div className="shortcut"><span className="key">Enter</span> Enviar</div>
        <div className="shortcut"><span className="key">Shift+Enter</span> Nueva linea</div>
        <div className="shortcut"><span className="key">Effort bar</span> Click para ciclar</div>
      </div>

      <h3 className="help-subtitle">Temas</h3>
      <p className="help-text">
        6 temas disponibles: Neon, Dracula, Monokai, Catppuccin, Gruvbox, Tokyo Night.
        Cambia en Settings.
      </p>
    </div>
  )
}
