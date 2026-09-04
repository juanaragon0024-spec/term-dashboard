# Term

Una terminal con IA que además actúa. Conecta Claude, GPT, Gemini, Grok o un
modelo local, y desde la misma ventana creas archivos, buscas, lanzas el
servidor de desarrollo, revisas el diff y confirmas el commit.

La idea es no tener que moverte: lo que normalmente te hace abrir otra ventana
—git, los logs de algo que está corriendo, buscar un archivo— cabe aquí.

## Instalar

Sin clonar nada, en un solo comando:

```bash
pip install "git+https://github.com/juanaragon0024-spec/term-dashboard.git#subdirectory=term"
term
```

El `#subdirectory=term` es necesario porque el paquete vive en `term/`, no en
la raíz del repositorio.

Para trastear con el código, clónalo e instálalo en modo editable, que hace que
los cambios se apliquen sin reinstalar:

```bash
git clone https://github.com/juanaragon0024-spec/term-dashboard.git
cd term-dashboard/term
pip install -e .
```

Para actualizar a la última versión:

```bash
pip install --upgrade --force-reinstall \
  "git+https://github.com/juanaragon0024-spec/term-dashboard.git#subdirectory=term"
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
| **Permisos** | `/permissions lectura\|normal\|todo` |

Todo en **10 idiomas** (`/lang`) y **6 temas** (`/theme`).

## Desarrollo

```bash
cd term
pip install -e ".[dev]"
pytest          # 479 tests
ruff check .
```

## Versión web (experimental)

La misma idea en el navegador, con memoria de conversación y coste real. Todo
en **una sola dirección**: el servidor sirve la interfaz y la API a la vez.

```bash
cd backend && npm install && npm start
```

Y abres **http://localhost:3001**. `npm start` construye la interfaz y arranca
el servidor; si solo quieres arrancarlo, `npm run serve`.

Para desarrollar con recarga en caliente, `cd frontend && npm run dev` levanta
Vite en el 5173 y reenvía `/api` al backend, así que sigues trabajando contra
una sola dirección.

El catálogo de comandos de la web se genera desde el de la terminal, para que
no puedan desincronizarse. Tras tocar `term/commands.py`:

```bash
python3 scripts/gen_commands.py
```

El servidor escucha solo en `127.0.0.1` y solo sirve archivos por debajo de
`TERM_ROOT`, que por defecto es tu carpeta personal:

```bash
TERM_ROOT=~/proyectos npm start    # acotarlo a lo que te interese
```
