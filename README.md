# Term

Una terminal con IA que además actúa. Conecta Claude, GPT, Gemini, Grok o un
modelo local, y desde la misma ventana creas archivos, buscas, lanzas el
servidor de desarrollo, revisas el diff y confirmas el commit.

La idea es no tener que moverte: lo que normalmente te hace abrir otra ventana
—git, los logs de algo que está corriendo, buscar un archivo— cabe aquí.

## Instalar

```bash
git clone https://github.com/juanaragon/term-dashboard.git
cd term-dashboard/term
pip install -e .
term
```

Necesitas **Python 3.10+**. Para el control del sistema (música, volumen, abrir
apps) hace falta macOS; el resto funciona en cualquier parte y lo que no está
disponible te lo dice en lugar de fallar en silencio.

## Conectar una IA

Hay dos formas, y `/providers` te enseña cuál tienes lista:

**Por línea de comandos** — la CLI trae su propio agente.

```bash
npm install -g @anthropic-ai/claude-code && claude auth login   # Claude Code
npm install -g opencode-ai                                      # opencode
```

**Por API** — aquí las herramientas las ejecuta Term. Con **OpenRouter** te
vale una sola clave para GPT, Gemini, Grok, Claude, Llama y cientos más:

```
/key openrouter sk-or-v1-...
/model openrouter/x-ai/grok-4
```

También hay conexión directa con OpenAI, Gemini, xAI, Groq, DeepSeek,
Anthropic y Ollama local. Las claves se guardan en `keys.json` con permisos
600, y se leen de las variables de entorno si ya las tienes exportadas.

**Cada pestaña es independiente**: su IA, su conversación y su gasto. Puedes
tener a Opus en una y a Gemini en otra sin que se enteren.

## Lo que sabe hacer

Se lo puedes pedir en lenguaje normal:

> «crea una carpeta notas y mete dentro un README»
> «busca dónde está el archivo de configuración»
> «por qué falla el build» — lee los logs del proceso que tienes corriendo
> «abre el navegador y busca vuelos a Lisboa»

Tiene doce herramientas propias (archivos, búsqueda, shell, música, web,
sistema) y habla **MCP**, así que puedes darle las de cualquier servidor
—GitHub, bases de datos, navegadores— sin escribir código:

```
/mcp-add github npx -y @modelcontextprotocol/server-github
```

Lee el `AGENTS.md` de tu repositorio y le pasa el esqueleto del código —clases
y funciones con su firma— para que sepa a qué llamar sin volcarle los archivos
enteros. En este proyecto eso cuesta 2.700 tokens en vez de 107.000.

## Atajos

| Tecla | Qué hace |
|---|---|
| `enter` / `alt+enter` | Enviar / salto de línea |
| `↑` `↓` · `tab` | Mensajes ya enviados · autocompletar |
| `ctrl+p` | Buscar un archivo y meterlo en el contexto |
| `ctrl+g` | Panel de git |
| `ctrl+t` · `ctrl+w` · `ctrl+1..9` | Nueva pestaña · cerrar · ir a la n |
| `ctrl+l` · `ctrl+e` · `ctrl+b` · `ctrl+y` | Limpiar · esfuerzo · archivos · copiar |
| `esc` | Cancelar o cerrar el panel |

## Comandos

Escribe `/` para verlos todos, o `/help` para la guía. Los que más se usan:

| | |
|---|---|
| **Trabajo** | `/bg` lanza sin bloquear · `/jobs` `/logs` `/stop` |
| **Git** | `/git` panel · `/diff` `/commit` `/undo` `/status` |
| **GitHub** | `/prs` `/issues` `/pr <n>` `/pr-checkout <n>` `/issue-new` |
| **Contexto** | `/add` `/drop` `/context` · `/outline` `/map` `/skeleton` |
| **IA** | `/model` `/providers` `/key` · `/architect` `/effort` |
| **Conversación** | `/sessions` `/resume` `/search` `/export` `/compact` |
| **Sistema** | `/run` `/open` `/web` `/play` `/volume` `/sysinfo` |
| **Permisos** | `/allow todo\|segura\|lectura\|nada` · `/permissions` |

Todo en **10 idiomas** (`/lang`) y **6 temas** (`/theme`).

## Desarrollo

```bash
cd term
pip install -e ".[dev]"
pytest          # 479 tests
ruff check .
```

## Versión web (experimental)

`backend/` y `frontend/` son la misma idea en el navegador, con memoria de
conversación y coste real. El backend solo escucha en `127.0.0.1`, solo acepta
el origen del frontend local y solo sirve archivos por debajo de `TERM_ROOT`.

```bash
cd backend  && npm install && node server.js
cd frontend && npm install && npm run dev   # y npm test
```
