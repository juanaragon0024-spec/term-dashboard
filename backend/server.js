const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

const SYSTEM_CONTEXT = `You are Term, a terminal AI assistant. You can control this macOS computer.
When the user asks you to open apps, change songs, adjust volume, etc., use osascript/AppleScript.

Examples:
- Open Safari: osascript -e 'tell application "Safari" to activate'
- Play/pause Spotify: osascript -e 'tell application "Spotify" to playpause'
- Next song: osascript -e 'tell application "Spotify" to next track'
- Set volume: osascript -e 'set volume output volume 50'
- Open any app: open -a "App Name"

You have full shell access. Execute commands directly. Be concise.`;

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.post('/api/chat', (req, res) => {
  const { message, workdir, model, effort } = req.body;

  if (!message) {
    return res.status(400).json({ error: 'Message is required' });
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const cwd = workdir || process.env.HOME;
  const fullPrompt = SYSTEM_CONTEXT + '\n\nUser request: ' + message;
  const args = ['-p', fullPrompt, '--max-turns', '15'];

  if (model && model !== 'claude') {
    const modelMap = { 'claude-opus': 'opus', 'claude-haiku': 'haiku' };
    const m = modelMap[model];
    if (m) args.push('--model', m);
  }
  if (effort) {
    args.push('--effort', effort);
  }

  const claude = spawn('claude', args, {
    cwd,
    env: { ...process.env },
    shell: true,
  });

  let fullOutput = '';
  let tokenEstimate = 0;

  claude.stdout.on('data', (data) => {
    const text = data.toString();
    fullOutput += text;
    tokenEstimate += text.split(/\s+/).length * 2;
    res.write(`data: ${JSON.stringify({ type: 'chunk', content: text, tokens: tokenEstimate })}\n\n`);
  });

  claude.stderr.on('data', (data) => {
    res.write(`data: ${JSON.stringify({ type: 'status', content: data.toString() })}\n\n`);
  });

  claude.on('close', (code) => {
    res.write(`data: ${JSON.stringify({ type: 'done', exitCode: code, tokens: tokenEstimate })}\n\n`);
    res.end();
  });

  claude.on('error', (err) => {
    res.write(`data: ${JSON.stringify({ type: 'error', content: err.message })}\n\n`);
    res.end();
  });

  req.on('close', () => { claude.kill(); });
});

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
