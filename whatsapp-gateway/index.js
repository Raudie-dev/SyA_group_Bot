// Gateway WhatsApp <-> Django
// - Restaura sesiones activas automáticamente al iniciar
// - Recibe mensajes de WhatsApp y los forwardea a Django (messages.upsert activo)
// - Cola de mensajes persistente: si WhatsApp está caído, encola y drena al reconectar
// - Endpoints /health y /queue para monitoreo y control

import 'dotenv/config';
import express from 'express';
import axios from 'axios';
import qrcode from 'qrcode-terminal';
import fs from 'fs';
import path from 'path';
import { makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';

const PORT = process.env.PORT || 3000;
const DJANGO_WEBHOOK = process.env.DJANGO_WEBHOOK || 'http://127.0.0.1:8000/api/whatsapp/webhook/';
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || 'pon-aqui-un-token-largo-y-aleatorio-32chars';
const QUEUE_FILE = './pending_queue.json';
const DRAIN_DELAY_MS = 5000; // 5 segundos entre mensajes al drainer

// Mapas por sesión (clave: "userId_slotId")
const sockets = new Map();
const latestQrs = new Map();
const statuses = new Map();
const backoffMap = new Map();

// Cola de mensajes pendientes: Map<sid, Array<{type, payload, addedAt}>>
const messageQueue = new Map();
const drainingSet = new Set(); // evitar drains concurrentes por sesión

// ─── Persistencia de cola ─────────────────────────────────────────────────────

function loadQueue() {
  try {
    if (fs.existsSync(QUEUE_FILE)) {
      const raw = JSON.parse(fs.readFileSync(QUEUE_FILE, 'utf-8'));
      for (const [sid, items] of Object.entries(raw)) {
        if (Array.isArray(items) && items.length > 0) {
          messageQueue.set(sid, items);
          console.log(`[Queue] Cargados ${items.length} mensaje(s) pendiente(s) para session=${sid}`);
        }
      }
    }
  } catch (e) {
    console.error('[Queue] Error cargando cola:', e.message);
  }
}

function saveQueue() {
  try {
    const obj = {};
    for (const [sid, items] of messageQueue.entries()) {
      if (items.length > 0) obj[sid] = items;
    }
    fs.writeFileSync(QUEUE_FILE, JSON.stringify(obj, null, 2), 'utf-8');
  } catch (e) {
    console.error('[Queue] Error guardando cola:', e.message);
  }
}

function enqueue(sid, item) {
  if (!messageQueue.has(sid)) messageQueue.set(sid, []);
  messageQueue.get(sid).push({ ...item, addedAt: new Date().toISOString() });
  saveQueue();
  console.log(`[Queue] Mensaje encolado para session=${sid}. Total pendientes: ${messageQueue.get(sid).length}`);
}

// ─── Drenado de cola ──────────────────────────────────────────────────────────

async function drainQueue(sid) {
  if (drainingSet.has(sid)) return;
  const queue = messageQueue.get(sid);
  if (!queue || queue.length === 0) return;

  drainingSet.add(sid);
  console.log(`[Queue] Iniciando drenado para session=${sid}. Mensajes pendientes: ${queue.length}`);

  while (queue.length > 0) {
    if (statuses.get(sid) !== 'connected') {
      console.log(`[Queue] Sesión ${sid} ya no conectada — pausando drenado.`);
      break;
    }
    const item = queue[0];
    const sock = sockets.get(sid);
    if (!sock) break;

    try {
      const jid = item.number.includes('@') ? item.number : `${item.number}@s.whatsapp.net`;
      if (item.type === 'text') {
        await sock.sendMessage(jid, { text: item.message });
      } else if (item.type === 'doc') {
        const buffer = Buffer.from(item.filedata, 'base64');
        if (item.message) await sock.sendMessage(jid, { text: item.message });
        await sock.sendMessage(jid, {
          document: buffer,
          mimetype: 'application/pdf',
          fileName: item.filename || 'consulta.pdf'
        });
      }
      queue.shift();
      saveQueue();
      console.log(`[Queue] Mensaje enviado. Restantes: ${queue.length}`);
    } catch (err) {
      console.error(`[Queue] Error enviando mensaje encolado:`, err.message);
      break;
    }

    if (queue.length > 0) {
      await new Promise(r => setTimeout(r, DRAIN_DELAY_MS));
    }
  }

  drainingSet.delete(sid);
  console.log(`[Queue] Drenado finalizado para session=${sid}. Restantes: ${messageQueue.get(sid)?.length || 0}`);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function sessionId(user, slot) {
  const u = user === undefined || user === null ? 'default' : String(user);
  const s = slot === undefined || slot === null ? '0' : String(slot);
  return `${u}_${s}`;
}

function extractMessageText(message) {
  if (!message) return '';
  if (message.conversation) return message.conversation;
  if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
  if (message.imageMessage?.caption) return message.imageMessage.caption;
  if (message.videoMessage?.caption) return message.videoMessage.caption;
  if (message.buttonsResponseMessage?.selectedButtonId) return message.buttonsResponseMessage.selectedButtonId;
  if (message.templateButtonReplyMessage?.selectedId) return message.templateButtonReplyMessage.selectedId;
  try { return JSON.stringify(message); } catch (e) { return ''; }
}

// ─── Socket WhatsApp ───────────────────────────────────────────────────────────

async function startSocketFor(sid = 'default_0') {
  try {
    const dir = `./auth_info/${sid}`;
    const { state, saveCreds } = await useMultiFileAuthState(dir);
    const { version } = await fetchLatestBaileysVersion();

    // Cerrar socket existente sin logout (logout invalida credenciales en WA)
    const existing = sockets.get(sid);
    if (existing) {
      try {
        if (existing?.ws && typeof existing.ws.close === 'function') existing.ws.close();
      } catch (e) {
        try { existing?.ev?.removeAllListeners && existing.ev.removeAllListeners(); } catch (e2) {}
      }
      sockets.delete(sid);
    }

    const sock = makeWASocket({ auth: state, version });
    sockets.set(sid, sock);
    latestQrs.set(sid, null);
    statuses.set(sid, 'initializing');

    sock.ev.on('creds.update', saveCreds);

    // ── Eventos de conexión ───────────────────────────────────────────────────
    sock.ev.on('connection.update', (update) => {
      const { connection, qr, lastDisconnect } = update;

      if (qr) {
        latestQrs.set(sid, qr);
        qrcode.generate(qr, { small: true });
        console.log(`[QR] Generado para session=${sid}`);
      }

      if (connection === 'open') {
        latestQrs.set(sid, null);
        statuses.set(sid, 'connected');
        backoffMap.delete(sid);
        console.log(`[WA] Conectado session=${sid}`);
        // Drainear mensajes que quedaron pendientes durante la desconexión
        drainQueue(sid);
      }

      if (connection === 'close') {
        statuses.set(sid, 'disconnected');

        // Detectar logout intencional para no reconectar (credenciales inválidas)
        let isIntentional = false;
        try {
          const err = lastDisconnect?.error;
          if (err?.output?.statusCode === 401) isIntentional = true;
          if (String(err?.message || err || '').toLowerCase().includes('intentional logout')) isIntentional = true;
          if (String(lastDisconnect || '').toLowerCase().includes('intentional logout')) isIntentional = true;
        } catch (e) {}

        if (isIntentional) {
          console.error(`[WA] Logout intencional session=${sid} — no reconectando.`);
          statuses.set(sid, 'unlinked');
          latestQrs.delete(sid);
          try { sockets.get(sid)?.ev?.removeAllListeners(); } catch (e) {}
          sockets.delete(sid);
          return;
        }

        const prev = backoffMap.get(sid) || 0;
        const attempts = Math.min(prev + 1, 6);
        backoffMap.set(sid, attempts);
        const delay = Math.min(30000, 1000 * Math.pow(2, attempts));
        console.log(`[WA] Desconectado session=${sid}. Reconectando en ${delay / 1000}s (intento ${attempts})...`);
        setTimeout(() => {
          startSocketFor(sid).catch(err => console.error('[WA] Error reconectando:', err));
        }, delay);
      }
    });

    // ── Recibir mensajes de WhatsApp y forwardear a Django ────────────────────
    sock.ev.on('messages.upsert', async (m) => {
      try {
        const msgs = m.messages || [];
        for (const msg of msgs) {
          if (!msg.message || msg.key?.fromMe) continue;
          if (msg.key.remoteJid?.endsWith('@g.us')) continue;
          if (msg.key.remoteJid === 'status@broadcast') continue;

          const remoteJid = msg.key.remoteJid || '';
          const pushName = msg.pushName || '';
          const messageText = extractMessageText(msg.message);
          if (!messageText) continue;

          const owner = String(sid).split('_')[0];
          console.log(`[WA] Mensaje recibido de ${remoteJid} (session=${sid}): "${messageText.slice(0, 80)}"`);

          try {
            const resp = await axios.post(
              DJANGO_WEBHOOK,
              { remoteJid, pushName, messageText, session: sid, owner },
              {
                headers: {
                  'Content-Type': 'application/json',
                  'X-Webhook-Secret': WEBHOOK_SECRET,
                },
                timeout: 25000,
              }
            );
            if (resp?.data?.reply?.trim()) {
              await sock.sendMessage(remoteJid, { text: resp.data.reply });
              console.log(`[WA] Respuesta enviada a ${remoteJid}`);
            }
          } catch (err) {
            console.error('[WA] Error en webhook/reply:', err.message || err);
          }
        }
      } catch (err) {
        console.error('[WA] Error procesando messages.upsert:', err);
      }
    });

    console.log(`[WA] Socket inicializado para session=${sid}`);
    return sock;
  } catch (err) {
    console.error('[WA] Error iniciando socket:', err);
    throw err;
  }
}

// ─── Restaurar sesiones al iniciar ────────────────────────────────────────────

async function restoreActiveSessions() {
  const authDir = './auth_info';
  if (!fs.existsSync(authDir)) {
    console.log('[WA] No existe directorio auth_info — sin sesiones previas.');
    return;
  }
  const sessionDirs = fs.readdirSync(authDir, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name);

  if (sessionDirs.length === 0) {
    console.log('[WA] No hay sesiones previas para restaurar.');
    return;
  }

  console.log(`[WA] Restaurando ${sessionDirs.length} sesión(es): ${sessionDirs.join(', ')}`);
  for (const sid of sessionDirs) {
    try {
      await startSocketFor(sid);
      // Pequeña pausa entre sesiones para no saturar los servidores de WA
      await new Promise(r => setTimeout(r, 2000));
    } catch (err) {
      console.error(`[WA] Error restaurando session=${sid}:`, err.message);
    }
  }
}

// ─── Servidor HTTP ─────────────────────────────────────────────────────────────

function startServer() {
  const app = express();
  app.use(express.json({ limit: '50mb' }));

  // GET /qr — obtener QR actual para una sesión
  app.get('/qr', (req, res) => {
    const sid = sessionId(req.query.user, req.query.slot);
    const qr = latestQrs.get(sid) || null;
    const status = statuses.get(sid) || 'disconnected';
    if (status === 'connected') return res.json({ qr: null, status, message: 'Conectado.' });
    if (!qr) return res.json({ qr: null, status, message: 'No QR disponible.' });
    return res.json({ qr, status });
  });

  // POST /generate — reinicia sesión y genera nuevo QR
  app.post('/generate', async (req, res) => {
    const sid = sessionId(req.query.user, req.query.slot);
    try {
      if (statuses.get(sid) === 'connected') {
        return res.json({ ok: true, message: 'Ya conectado', qr: null });
      }
      const dir = path.resolve(`./auth_info/${sid}`);
      if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
      await startSocketFor(sid);

      const maxWait = 10000;
      const interval = 500;
      let waited = 0;
      let qr = latestQrs.get(sid) || null;
      while (!qr && waited < maxWait) {
        await new Promise(r => setTimeout(r, interval));
        waited += interval;
        qr = latestQrs.get(sid) || null;
      }
      return res.json({ ok: true, qr });
    } catch (err) {
      console.error('[/generate] Error:', err);
      return res.status(500).json({ ok: false, error: String(err) });
    }
  });

  // POST /unlink — desvincular teléfono y borrar credenciales
  app.post('/unlink', async (req, res) => {
    const sid = sessionId(req.query.user, req.query.slot);
    try {
      const sock = sockets.get(sid);
      if (sock) {
        try { if (sock?.ws?.close) sock.ws.close(); } catch (e) {
          try { sock?.ev?.removeAllListeners && sock.ev.removeAllListeners(); } catch (e2) {}
        }
        sockets.delete(sid);
      }
      const dir = path.resolve(`./auth_info/${sid}`);
      if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
      latestQrs.delete(sid);
      statuses.set(sid, 'unlinked');
      backoffMap.delete(sid);
      return res.json({ ok: true, message: `Desvinculado session=${sid}` });
    } catch (err) {
      console.error('[/unlink] Error:', err);
      return res.status(500).json({ ok: false, error: String(err) });
    }
  });

  // POST /send — enviar texto; encola si está desconectado
  app.post('/send', async (req, res) => {
    const { number, message } = req.body || {};
    const sid = sessionId(req.query.user || req.body.user, req.query.slot || req.body.slot);
    if (!number || !message) return res.status(400).json({ error: 'Faltan campos: number y message' });

    const sock = sockets.get(sid);
    if (!sock || statuses.get(sid) !== 'connected') {
      enqueue(sid, { type: 'text', number, message });
      return res.json({ ok: true, queued: true, message: 'Sesión desconectada — mensaje encolado.' });
    }

    try {
      const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
      await sock.sendMessage(jid, { text: message });
      return res.json({ ok: true, queued: false });
    } catch (err) {
      console.error('[/send] Error:', err.message);
      enqueue(sid, { type: 'text', number, message });
      return res.json({ ok: true, queued: true, message: 'Error al enviar — mensaje encolado.' });
    }
  });

  // POST /send-doc — enviar PDF; encola si está desconectado
  app.post('/send-doc', async (req, res) => {
    const { number, message, filename, filedata } = req.body || {};
    const sid = sessionId(req.query.user || req.body.user, req.query.slot || req.body.slot);
    if (!number || !filedata) return res.status(400).json({ error: 'Faltan campos: number y filedata' });

    const sock = sockets.get(sid);
    if (!sock || statuses.get(sid) !== 'connected') {
      enqueue(sid, { type: 'doc', number, message, filename, filedata });
      return res.json({ ok: true, queued: true, message: 'Sesión desconectada — documento encolado.' });
    }

    try {
      const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
      const buffer = Buffer.from(filedata, 'base64');
      if (message) await sock.sendMessage(jid, { text: message });
      await sock.sendMessage(jid, {
        document: buffer,
        mimetype: 'application/pdf',
        fileName: filename || 'consulta.pdf'
      });
      return res.json({ ok: true, queued: false });
    } catch (err) {
      console.error('[/send-doc] Error:', err.message);
      enqueue(sid, { type: 'doc', number, message, filename, filedata });
      return res.json({ ok: true, queued: true, message: 'Error al enviar — documento encolado.' });
    }
  });

  // GET /status — estado de una sesión específica
  app.get('/status', (req, res) => {
    const sid = sessionId(req.query.user, req.query.slot);
    const status = statuses.get(sid) || 'disconnected';
    const pending = messageQueue.get(sid)?.length || 0;
    return res.json({ status, pending_messages: pending });
  });

  // GET /health — estado de todas las sesiones (para monitoreo)
  app.get('/health', (req, res) => {
    const sessions = {};
    for (const [sid, status] of statuses.entries()) {
      sessions[sid] = {
        status,
        pending_messages: messageQueue.get(sid)?.length || 0,
      };
    }
    return res.json({ ok: true, sessions });
  });

  // GET /queue/status — ver mensajes pendientes en cola
  app.get('/queue/status', (req, res) => {
    if (req.query.user && req.query.slot) {
      const sid = sessionId(req.query.user, req.query.slot);
      const queue = messageQueue.get(sid) || [];
      return res.json({ sid, pending: queue.length, messages: queue });
    }
    const all = {};
    for (const [sid, items] of messageQueue.entries()) {
      all[sid] = { pending: items.length };
    }
    return res.json(all);
  });

  // POST /queue/drain — forzar drenado manual de la cola
  app.post('/queue/drain', async (req, res) => {
    const sid = sessionId(req.query.user || req.body?.user, req.query.slot || req.body?.slot);
    if (statuses.get(sid) !== 'connected') {
      return res.status(400).json({ ok: false, error: `Sesión ${sid} no está conectada.` });
    }
    const pending = messageQueue.get(sid)?.length || 0;
    drainQueue(sid);
    return res.json({ ok: true, message: `Drenando ${pending} mensaje(s) para session=${sid}` });
  });

  app.listen(PORT, () => console.log(`[Gateway] Escuchando en http://localhost:${PORT}`));
}

// ─── Arranque ─────────────────────────────────────────────────────────────────

(async () => {
  try {
    loadQueue();
    startServer();
    await restoreActiveSessions();
  } catch (err) {
    console.error('[Gateway] Fallo en el arranque:', err);
    process.exit(1);
  }
})();
