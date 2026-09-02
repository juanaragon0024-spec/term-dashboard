const express = require('express');
const cors = require('cors');
const { spawn, execSync } = require('child_process');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// Resolve claude path at startup
let CLAUDE = 'claude';
try {
  CLAUDE = execSync('bash -lc "which claude"', { encoding: 'utf-8' }).trim();
} catch {}
console.log('Claude path:', CLAUDE);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', claude: CLAUDE });
});

app.get('/api/file', (req, res) => {
  const filePath = req.query.path;
  if (!filePath) return res.status(400).json({ error: 'path required' });
  const fs = require('fs');
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    res.json({ path: filePath, content });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/files', (req, res) => {
  const dir = req.query.path || process.env.HOME;
  const fs = require('fs');
  try {
    const items = fs.readdirSync(dir, { withFileTypes: true }).map(d => ({
      name: d.name,
      isDir: d.isDirectory(),
    }));
    res.json({ path: dir, items });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/chat', (req, res) => {
  const { message, workdir, model, effort } = req.body;
  console.log('POST /api/chat:', message?.substring(0, 50));

  if (!message) {
    return res.status(400).json({ error: 'Message is required' });
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const cwd = workdir || process.env.HOME;
  const args = ['-p', message, '--max-turns', '15'];

  if (model && model !== 'claude') {
    const modelMap = { 'claude-opus': 'opus', 'claude-haiku': 'haiku' };
    const m = modelMap[model];
    if (m) args.push('--model', m);
  }
  if (effort) {
    args.push('--effort', effort);
  }

  console.log('Spawning:', CLAUDE, args.join(' '));

  const claude = spawn(CLAUDE, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env },
  });

  let tokenEstimate = 0;
  let finished = false;

  claude.stdout.on('data', (data) => {
    if (finished) return;
    const text = data.toString();
    console.log('stdout chunk:', text.length, 'bytes');
    tokenEstimate += text.split(/\s+/).length * 2;
    res.write(`data: ${JSON.stringify({ type: 'chunk', content: text, tokens: tokenEstimate })}\n\n`);
  });

  claude.stderr.on('data', (data) => {
    console.log('stderr:', data.toString().substring(0, 100));
  });

  claude.on('close', (code) => {
    console.log('claude exited:', code);
    if (finished) return;
    finished = true;
    res.write(`data: ${JSON.stringify({ type: 'done', exitCode: code, tokens: tokenEstimate })}\n\n`);
    res.end();
  });

  claude.on('error', (err) => {
    console.error('spawn error:', err.message);
    if (finished) return;
    finished = true;
    res.write(`data: ${JSON.stringify({ type: 'error', content: err.message })}\n\n`);
    res.end();
  });

  // Kill claude only if client actually disconnects mid-stream
  res.on('close', () => {
    if (!finished) {
      finished = true;
      try { claude.kill(); } catch {}
    }
  });
});

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
