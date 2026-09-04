/**
 * Comprobaciones del servidor contra un servidor de verdad.
 *
 * Existen por un fallo concreto: la interfaz se quedaba en blanco porque la
 * lista de orígenes permitidos no incluía al propio servidor. curl no manda
 * cabecera Origin, así que las comprobaciones con curl daban 200 y el fallo
 * pasó desapercibido; el navegador sí la manda al cargar módulos ES.
 */

import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { after, before, describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const PUERTO = 3199;
const BASE = `http://localhost:${PUERTO}`;

let servidor;

before(async () => {
  servidor = spawn('node', [path.join(AQUI, '..', 'server.js')], {
    env: { ...process.env, PORT: String(PUERTO) },
    stdio: 'ignore',
  });
  // Esperar a que conteste, en vez de dormir a ojo.
  for (let i = 0; i < 50; i++) {
    try {
      await fetch(`${BASE}/api/health`);
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 100));
    }
  }
  throw new Error('el servidor no arrancó');
});

after(() => servidor?.kill());

describe('orígenes', () => {
  it('acepta el suyo propio, que es el que manda el navegador', async () => {
    for (const origen of [`http://localhost:${PUERTO}`, `http://127.0.0.1:${PUERTO}`]) {
      const res = await fetch(`${BASE}/api/health`, { headers: { Origin: origen } });
      assert.equal(res.status, 200, `rechazó ${origen}`);
      assert.equal(res.headers.get('access-control-allow-origin'), origen);
    }
  });

  it('acepta el de Vite, para desarrollar con recarga en caliente', async () => {
    const res = await fetch(`${BASE}/api/health`, {
      headers: { Origin: 'http://localhost:5173' },
    });
    assert.equal(res.headers.get('access-control-allow-origin'), 'http://localhost:5173');
  });

  it('no da permiso a un origen ajeno', async () => {
    const res = await fetch(`${BASE}/api/health`, {
      headers: { Origin: 'https://sitio-ajeno.example' },
    });
    // Responde, pero sin la cabecera: es el navegador quien bloquea.
    assert.equal(res.headers.get('access-control-allow-origin'), null);
  });

  it('sin cabecera Origin también responde', async () => {
    assert.equal((await fetch(`${BASE}/api/health`)).status, 200);
  });
});

describe('rutas', () => {
  it('la salud dice qué claude usa y con qué raíz', async () => {
    const datos = await (await fetch(`${BASE}/api/health`)).json();
    assert.equal(datos.status, 'ok');
    assert.ok(datos.root);
  });

  it('no sirve nada fuera de la raíz permitida', async () => {
    for (const ruta of ['/etc/passwd', '../../../etc/passwd', '..']) {
      const res = await fetch(`${BASE}/api/file?path=${encodeURIComponent(ruta)}`);
      assert.equal(res.status, 403, `dejó pasar ${ruta}`);
    }
  });

  it('un chat sin mensaje se rechaza', async () => {
    const res = await fetch(`${BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    assert.equal(res.status, 400);
  });
});
