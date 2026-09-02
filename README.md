# Term

Multi-AI TUI dashboard para terminal. Colores vivos, syntax highlighting, temas, control del sistema.

## Instalar

```bash
pip install git+https://github.com/juanaragon/term-dashboard.git#subdirectory=term
```

O clonar e instalar local:

```bash
git clone https://github.com/juanaragon/term-dashboard.git
cd term-dashboard/term
pip install -e .
```

## Usar

```bash
term
```

Con directorio de trabajo:

```bash
term -w ~/mi-proyecto
```

Con tema:

```bash
term -t dracula
```

## Requisitos

- Python 3.10+
- Claude Code CLI con OAuth (`npm install -g @anthropic-ai/claude-code && claude auth login`)

## Features

- Chat con Claude via CLI OAuth (Sonnet, Opus, Haiku)
- 6 temas: Neon, Dracula, Monokai, Catppuccin, Gruvbox, Tokyo Night
- Pestanas multiples con nombre y modelo por tab
- 25+ comandos (escribe `/` para ver la lista)
- Control del sistema macOS (abrir apps, Spotify, volumen)
- Barra de contexto con tokens estimados
- Selector de effort (low/medium/high/max)
- Panel de apps, tools, settings, help
- Config persistente en ~/.config/term/config.json

## Comandos

| Comando | Descripcion |
|---------|-------------|
| `/theme <name>` | Cambiar tema |
| `/effort <level>` | Cambiar esfuerzo |
| `/model <name>` | Cambiar modelo |
| `/new [nombre] [modelo]` | Nueva tab con selector de modelo |
| `/name <texto>` | Renombrar tab activa |
| `/close` | Cerrar tab |
| `/clear` | Limpiar chat |
| `/open <app>` | Abrir aplicacion |
| `/run <cmd>` | Ejecutar comando shell |
| `/volume <0-100>` | Ajustar volumen |
| `/play` | Play/pause Spotify |
| `/next` `/prev` | Siguiente/anterior cancion |
| `/models` | Listar modelos |
| `/themes` | Listar temas |
| `/status` | Estado actual |
| `/help` | Ayuda completa |
| `/` | Lista de comandos |
