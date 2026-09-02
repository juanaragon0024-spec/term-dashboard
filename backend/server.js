const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Chat endpoint - streams Claude Code output
app.post('/api/chat', (req, res) => {
  const { message, workdir, model, effort } = req.body;

  if (!message) {
    return res.status(400).json({ error: 'Message is required' });
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const cwd = workdir || process.env.HOME;

  const args = ['-p', message, '--max-turns', '15'];
  if (model && model !== 'claude') {
    const modelMap = { 'claude-opus': 'opus', 'claude-haiku': 'haiku' };
    const m = modelMap[model];
    if (m) args.push('--model', m);
  }
  if (effort && effort !== 'high') {
    args.push('--effort', effort);
  }

  const claude = spawn('claude', args, {
    cwd,
    env: { ...process.env },
    shell: true,
  });

  let fullOutput = '';

  claude.stdout.on('data', (data) => {
    const text = data.toString();
    fullOutput += text;
    res.write(`data: ${JSON.stringify({ type: 'chunk', content: text })}\n\n`);
  });

  claude.stderr.on('data', (data) => {
    const text = data.toString();
    // Claude CLI writes progress to stderr, forward it
    res.write(`data: ${JSON.stringify({ type: 'status', content: text })}\n\n`);
  });

  claude.on('close', (code) => {
    res.write(`data: ${JSON.stringify({ type: 'done', exitCode: code })}\n\n`);
    res.end();
  });

  claude.on('error', (err) => {
    res.write(`data: ${JSON.stringify({ type: 'error', content: err.message })}\n\n`);
    res.end();
  });

  // Handle client disconnect
  req.on('close', () => {
    claude.kill();
  });
});

// List files in a directory
app.get('/api/files', (req, res) => {
  const dir = req.query.path || process.env.HOME;
  const { execSync } = require('child_process');
  try {
    const output = execSync(`ls -la "${dir}"`, { encoding: 'utf-8' });
    res.json({ path: dir, content: output });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Read a file
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

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
