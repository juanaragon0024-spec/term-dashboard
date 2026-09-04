'use strict';

/**
 * Backend de la versión web de Term.
 *
 * Sirve la API y también la interfaz ya construida, así que todo vive en un
 * solo puerto: una única dirección que abrir y sin CORS de por medio, porque
 * las peticiones salen del mismo origen.
 *
 * Este proceso puede leer ficheros y lanzar la CLI de Claude, así que solo
 * sirve rutas que cuelguen de un directorio raíz explícito. Antes /api/file
 * servía cualquier ruta del sistema con CORS abierto a todo: cualquier web que
 * el usuario visitase mientras el backend corría podía leerle las claves SSH.
 */

const express = require('express');
const cors = require('cors');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { spawn, execFileSync } = require('child_process');

const app = express();
const PORT = Number(process.env.PORT) || 3001;

// Raíz permitida. Todo lo que se sirva tiene que estar dentro.
const ROOT = path.resolve(process.env.TERM_ROOT || os.homedir());

// La interfaz construida. Al servirla desde aquí, el navegador y la API
// comparten origen y no hace falta CORS.
const UI_DIR = path.resolve(__dirname, '..', 'frontend', 'dist');
const UI_BUILT = fs.existsSync(path.join(UI_DIR, 'index.html'));

// En desarrollo la interfaz la sirve Vite en otro puerto, y solo entonces
// hace falta permitir ese origen. Sin esto, cualquier página abierta en el
// navegador podría llamar a esta API con las credenciales del usuario.
const DEV_ORIGINS = new Set([
  'http://localhost:5173', 'http://127.0.0.1:5173',
  'http://localhost:4173', 'http://127.0.0.1:4173',
]);

app.use(cors({
  origin(origin, callback) {
    if (!origin || DEV_ORIGINS.has(origin)) return callback(null, true);
    return callback(new Error('origen no permitido'));
  },
}));
app.use(express.json({ limit: '1mb' }));

if (UI_BUILT) {
  app.use(express.static(UI_DIR));
}

// Resolver la ruta de claude una sola vez, sin pasar por una shell.
let CLAUDE = 'claude';
try {
  CLAUDE = execFileSync('which', ['claude'], { encoding: 'utf-8' }).trim() || 'claude';
} catch {
  // Se queda en 'claude' y el spawn dirá si no existe.
}

/**
 * Resolver una ruta pedida por el cliente dentro de ROOT.
 * Devuelve null si se sale, incluso vía ../ o enlaces simbólicos.
 */
function safeResolve(requested) {
  const target = path.resolve(ROOT, requested || '.');
  let real;
  try {
    real = fs.realpathSync(target);
  } catch {
    real = target; // aún no existe: basta con comprobar la ruta normalizada
  }
  const rootReal = fs.realpathSync(ROOT);
  if (real !== rootReal && !real.startsWith(rootReal + path.sep)) return null;
  return real;
}

// Tope de lectura: sin esto, pedir un fichero de varios GB tumba el proceso.
const MAX_FILE_BYTES = 2 * 1024 * 1024;

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', claude: CLAUDE, root: ROOT });
});

app.get('/api/file', (req, res) => {
  const resolved = safeResolve(req.query.path);
  if (!resolved) return res.status(403).json({ error: 'ruta fuera del directorio permitido' });
  let stat;
  try {
    stat = fs.statSync(resolved);
  } catch {
    return res.status(404).json({ error: 'no encontrado' });
  }
  if (!stat.isFile()) return res.status(400).json({ error: 'no es un fichero' });
  if (stat.size > MAX_FILE_BYTES) return res.status(413).json({ error: 'fichero demasiado grande' });
  try {
    res.json({ path: resolved, content: fs.readFileSync(resolved, 'utf-8') });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/files', (req, res) => {
  const resolved = safeResolve(req.query.path);
  if (!resolved) return res.status(403).json({ error: 'ruta fuera del directorio permitido' });
  try {
    const items = fs.readdirSync(resolved, { withFileTypes: true })
      .filter((d) => !d.name.startsWith('.'))
      .map((d) => ({ name: d.name, isDir: d.isDirectory() }))
      .sort((a, b) => (a.isDir === b.isDir ? a.name.localeCompare(b.name) : a.isDir ? -1 : 1));
    res.json({ path: resolved, items });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const EFFORT_LEVELS = new Set(['low', 'medium', 'high', 'max']);
const MODEL_ALIASES = { opus: 'opus', sonnet: 'sonnet', haiku: 'haiku' };

app.post('/api/chat', (req, res) => {
  const { message, workdir, model, effort, sessionId, resume } = req.body || {};
  if (typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message es obligatorio' });
  }

  const cwd = safeResolve(workdir) || ROOT;
  const id = typeof sessionId === 'string' && /^[0-9a-f-]{36}$/i.test(sessionId)
    ? sessionId
    : crypto.randomUUID();

  // Igual que la TUI: la conversación se abre con --session-id y los turnos
  // siguientes la continúan con --resume, que es lo que da memoria al chat.
  const args = ['-p', message];
  args.push(resume ? '--resume' : '--session-id', id);
  args.push('--output-format', 'stream-json', '--include-partial-messages', '--verbose');
  args.push('--max-turns', '15');

  const alias = MODEL_ALIASES[model];
  if (alias) args.push('--model', alias);
  if (EFFORT_LEVELS.has(effort)) args.push('--effort', effort);

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const claude = spawn(CLAUDE, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });

  let finished = false;
  let buffer = '';

  const send = (payload) => {
    if (!finished) res.write(`data: ${JSON.stringify(payload)}\n\n`);
  };

  send({ type: 'session', sessionId: id });

  claude.stdout.on('data', (data) => {
    buffer += data.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // la última puede venir a medias
    for (const line of lines) {
      if (!line.trim()) continue;
      let event;
      try {
        event = JSON.parse(line);
      } catch {
        continue;
      }
      if (event.type === 'stream_event') {
        const delta = event.event?.delta;
        if (delta?.type === 'text_delta') send({ type: 'chunk', content: delta.text });
      } else if (event.type === 'assistant') {
        for (const block of event.message?.content || []) {
          if (block?.type === 'tool_use') send({ type: 'tool', name: block.name });
        }
      } else if (event.type === 'result') {
        const usage = event.usage || {};
        send({
          type: 'usage',
          // Tokens y coste reales, en vez de la estimación por palabras.
          tokens: (usage.input_tokens || 0) + (usage.output_tokens || 0)
            + (usage.cache_read_input_tokens || 0) + (usage.cache_creation_input_tokens || 0),
          cost: event.total_cost_usd || 0,
          contextWindow: Object.values(event.modelUsage || {})[0]?.contextWindow || 0,
          text: event.result || '',
        });
      }
    }
  });

  // stderr se consume siempre: si se dejara sin leer, el pipe se llenaría y el
  // proceso se quedaría bloqueado a mitad de respuesta.
  let stderr = '';
  claude.stderr.on('data', (data) => {
    if (stderr.length < 8000) stderr += data.toString();
  });

  claude.on('close', (code) => {
    if (finished) return;
    if (code !== 0 && stderr.trim()) send({ type: 'error', content: stderr.trim() });
    send({ type: 'done', exitCode: code });
    finished = true;
    res.end();
  });

  claude.on('error', (err) => {
    if (finished) return;
    send({ type: 'error', content: err.message });
    finished = true;
    res.end();
  });

  res.on('close', () => {
    if (!finished) {
      finished = true;
      try { claude.kill(); } catch { /* ya había terminado */ }
    }
  });
});

// Cualquier ruta que no sea de la API la resuelve la interfaz, que lleva su
// propio enrutado en el navegador.
if (UI_BUILT) {
  app.get(/^\/(?!api\/).*/, (req, res) => {
    res.sendFile(path.join(UI_DIR, 'index.html'));
  });
}

app.listen(PORT, '127.0.0.1', () => {
  console.log(`\n  Term  →  http://localhost:${PORT}`);
  console.log(`  raíz: ${ROOT}`);
  if (!UI_BUILT) {
    console.log('\n  La interfaz no está construida todavía:');
    console.log('    cd frontend && npm install && npm run build');
    console.log('  Mientras tanto solo responde la API en /api/*.');
  }
  console.log('');
});
