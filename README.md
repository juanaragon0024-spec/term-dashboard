# Term

TUI multipestaña sobre la CLI de Claude Code. Colores vivos, temas, sesiones con
memoria y control del sistema, todo desde la terminal.

## Instalar

```bash
git clone https://github.com/juanaragon/term-dashboard.git
cd term-dashboard/term
pip install -e .
```

## Usar

```bash
term                      # en el directorio actual
term -w ~/mi-proyecto     # con directorio de trabajo
term -t dracula           # con tema
term -l en                # con idioma
```

## Requisitos

- Python 3.10+
- Claude Code CLI autenticado: `npm install -g @anthropic-ai/claude-code && claude auth login`
- macOS para el control del sistema (Spotify, volumen, abrir apps). El resto
  funciona en cualquier plataforma y las funciones no disponibles lo dicen en
  lugar de fallar en silencio.

## Qué hace

- **Conversaciones con memoria.** Cada pestaña mantiene su sesión, así que
  Claude recuerda lo que le has dicho antes. Se retoman con `/sessions` y
  `/resume`.
- **Streaming con herramientas a la vista.** Verás cuándo Claude lee un
  fichero, ejecuta algo o busca, no solo el texto final.
- **Tokens y coste reales**, leídos de la CLI en vez de estimados.
- **Entrada de varias líneas**: Enter envía, alt+Enter salta de línea.
- **Historial** con las flechas y autocompletado de comandos con Tab.
- **6 temas** que se cambian en caliente: Neon, Dracula, Monokai, Catppuccin,
  Gruvbox, Tokyo Night.
- **10 idiomas** traducidos de verdad: es, en, pt, fr, de, it, zh, ja, ko, ar.
- **Rama de git** en la barra de estado.
- **Permisos con efecto**: si los rechazas, la CLI se lanza en modo restringido
  y `/run` no ejecuta nada.
- Config guardada sola en `~/.config/term/config.json`.

## Comandos

Escribe `/` para verlos todos. Los más usados:

| Comando | Qué hace |
|---|---|
| `/new [nombre] [modelo]` | Nueva pestaña |
| `/clear` | Limpiar el chat y empezar sesión nueva |
| `/sessions` · `/resume <n>` | Listar y retomar conversaciones |
| `/search <texto>` | Buscar en la conversación |
| `/model <nombre\|id>` | `default`, `opus`, `sonnet`, `haiku` o un id concreto |
| `/effort <nivel>` | `low`, `medium`, `high`, `max` |
| `/theme <nombre>` · `/lang <código>` | Tema e idioma |
| `/permissions <modo>` | `default`, `acceptEdits`, `plan`, `bypassPermissions` |
| `/attach <ruta>` · `/detach` | Adjuntar ficheros al siguiente mensaje |
| `/copy` · `/code [n]` | Copiar la respuesta o un bloque de código suelto |
| `/export` | Guardar la conversación en Markdown |
| `/run <cmd>` · `/open <app>` · `/volume <0-100>` | Sistema |
| `/play` · `/next` · `/prev` · `/track` | Spotify |

## Atajos

| Tecla | Qué hace |
|---|---|
| `enter` / `alt+enter` | Enviar / salto de línea |
| `↑` `↓` | Mensajes ya enviados |
| `tab` | Autocompletar comando |
| `ctrl+t` / `ctrl+w` | Nueva pestaña / cerrar pestaña o panel |
| `ctrl+1..9` | Ir a la pestaña n |
| `ctrl+l` / `ctrl+e` / `ctrl+b` / `ctrl+y` | Limpiar / esfuerzo / archivos / copiar |
| `esc` | Cancelar la generación o cerrar el panel |

## Desarrollo

```bash
cd term
pip install -e ".[dev]"
pytest          # 154 tests
ruff check .
```

## Versión web (experimental)

`backend/` y `frontend/` son una versión en el navegador de lo mismo. El backend
solo escucha en `127.0.0.1`, solo acepta el origen del frontend local y solo
sirve ficheros por debajo de `TERM_ROOT` (por defecto, tu carpeta personal).

```bash
cd backend && npm install && node server.js
cd frontend && npm install && npm run dev
```
