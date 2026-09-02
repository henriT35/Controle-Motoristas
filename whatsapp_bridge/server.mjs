import fs from 'node:fs'
import fsp from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

import makeWASocket, * as Baileys from '@whiskeysockets/baileys'
import pino from 'pino'
import QRCode from 'qrcode'

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url))
const BASE_DIR = path.resolve(process.env.PANEL_BASE_DIR || path.join(MODULE_DIR, '..'))
const RUNTIME_DIR = path.join(BASE_DIR, 'local_data', 'whatsapp')
const AUTH_DIR = path.join(RUNTIME_DIR, 'baileys_auth')
const STATE_FILE = path.join(RUNTIME_DIR, 'state.json')
const STOP_FILE = path.join(RUNTIME_DIR, 'stop.request')
const RESET_FILE = path.join(RUNTIME_DIR, 'reset.request')
const QR_FILE = path.join(RUNTIME_DIR, 'qr.png')
const TOKEN_FILE = path.join(RUNTIME_DIR, 'bridge_token.txt')
const INTERNAL_URL = String(process.env.PANEL_INTERNAL_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const HEARTBEAT_MS = 5000
const QUEUE_POLL_MS = 1300
const SEND_DELAY_MS = Math.max(1000, Number(process.env.WHATSAPP_SEND_DELAY_MS || 2500))
const RECONNECT_MS = 2500

await fsp.mkdir(RUNTIME_DIR, { recursive: true })
await fsp.mkdir(AUTH_DIR, { recursive: true })

const logger = pino({ level: process.env.WHATSAPP_BAILEYS_LOG_LEVEL || 'warn' })
const { DisconnectReason, useMultiFileAuthState } = Baileys
let socket = null
let connected = false
let stopping = false
let connecting = false
let resetting = false
let reconnectTimer = null
let queueBusy = false
let account = null
let qrCounter = 0
let stateWriteChain = Promise.resolve()

function nowIso() {
  return new Date().toISOString()
}

async function readJson(file, fallback = {}) {
  try {
    return JSON.parse(await fsp.readFile(file, 'utf8'))
  } catch {
    return fallback
  }
}

function writeState(values = {}) {
  stateWriteChain = stateWriteChain.then(async () => {
    const current = await readJson(STATE_FILE, {})
    const data = {
      ...current,
      ...values,
      pid: process.pid,
      backend: 'Baileys / Node.js',
      online: !stopping,
      heartbeat: nowIso(),
      qr_available: fs.existsSync(QR_FILE),
    }
    const tmp = path.join(RUNTIME_DIR, `state.${process.pid}.${Date.now()}.tmp`)
    await fsp.writeFile(tmp, JSON.stringify(data, null, 2), 'utf8')
    await fsp.rename(tmp, STATE_FILE)
  })
  return stateWriteChain
}

async function removeQr() {
  try { await fsp.unlink(QR_FILE) } catch {}
}

async function ensureToken() {
  try {
    const token = (await fsp.readFile(TOKEN_FILE, 'utf8')).trim()
    if (token.length >= 32) return token
  } catch {}
  const token = crypto.randomBytes(48).toString('base64url')
  await fsp.writeFile(TOKEN_FILE, token, { encoding: 'utf8', mode: 0o600 })
  return token
}

const BRIDGE_TOKEN = await ensureToken()

function disconnectStatusCode(lastDisconnect) {
  const error = lastDisconnect?.error
  return error?.output?.statusCode ?? error?.statusCode ?? error?.data?.statusCode ?? null
}

function safeAccount(sock) {
  const user = sock?.user || null
  if (!user) return null
  return {
    jid: String(user.id || ''),
    name: String(user.name || ''),
  }
}

async function renderQr(qr) {
  qrCounter += 1
  const tmp = path.join(RUNTIME_DIR, `qr.${process.pid}.${qrCounter}.png`)
  await QRCode.toFile(tmp, qr, {
    type: 'png',
    width: 460,
    margin: 2,
    errorCorrectionLevel: 'M',
  })
  let lastError = null
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      try { await fsp.unlink(QR_FILE) } catch {}
      await fsp.rename(tmp, QR_FILE)
      return
    } catch (error) {
      lastError = error
      await new Promise(resolve => setTimeout(resolve, 120))
    }
  }
  try { await fsp.unlink(tmp) } catch {}
  throw lastError || new Error('Não foi possível publicar o QR Code')
}

async function startSocket() {
  if (stopping || connecting) return
  connecting = true
  try {
    await writeState({
      status: 'STARTING',
      connected: false,
      message: 'Conectando diretamente ao WhatsApp pelo Baileys…',
      error_code: '',
    })

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)
    let version
    try {
      const fetchVersion = Baileys.fetchLatestWaWebVersion || Baileys.fetchLatestBaileysVersion
      if (typeof fetchVersion === 'function') {
        const latest = await fetchVersion()
        version = latest?.version
      }
    } catch (error) {
      logger.warn({ err: error }, 'Falha ao consultar versão mais recente do protocolo; usando padrão do Baileys')
    }

    socket = makeWASocket({
      ...(version ? { version } : {}),
      auth: state,
      logger,
      markOnlineOnConnect: false,
      syncFullHistory: false,
      generateHighQualityLinkPreview: false,
      shouldSyncHistoryMessage: () => false,
      getMessage: async () => undefined,
    })

    socket.ev.on('creds.update', saveCreds)
    socket.ev.on('connection.update', async (update) => {
      try {
        const { connection, qr, lastDisconnect } = update

        if (qr) {
          await renderQr(qr)
          connected = false
          await writeState({
            status: 'WAITING_QR',
            connected: false,
            message: 'QR Code pronto. Escaneie em WhatsApp → Aparelhos conectados.',
            qr_generated_at: nowIso(),
            qr_sequence: qrCounter,
            error_code: '',
          })
        }

        if (connection === 'open') {
          connected = true
          account = safeAccount(socket)
          await removeQr()
          await writeState({
            status: 'CONNECTED',
            connected: true,
            message: 'WhatsApp conectado e pronto para enviar.',
            connected_at: nowIso(),
            account_jid: account?.jid || '',
            account_name: account?.name || '',
            error_code: '',
          })
        }

        if (connection === 'close') {
          connected = false
          const statusCode = disconnectStatusCode(lastDisconnect)
          const loggedOut = statusCode === DisconnectReason.loggedOut
          if (loggedOut) {
            await removeQr()
            await writeState({
              status: 'LOGGED_OUT',
              connected: false,
              message: 'A sessão foi desconectada pelo WhatsApp. Use Novo pareamento para gerar outro QR Code.',
              error_code: 'BAILEYS_LOGGED_OUT',
              disconnect_status: statusCode,
            })
            return
          }

          if (!stopping && !resetting) {
            await writeState({
              status: 'RECONNECTING',
              connected: false,
              message: 'Conexão caiu. O Baileys está reconectando automaticamente…',
              error_code: '',
              disconnect_status: statusCode,
            })
            clearTimeout(reconnectTimer)
            reconnectTimer = setTimeout(() => {
              socket = null
              startSocket().catch((error) => fatalError(error))
            }, RECONNECT_MS)
          }
        }
      } catch (error) {
        await fatalError(error)
      }
    })
  } catch (error) {
    await fatalError(error)
  } finally {
    connecting = false
  }
}

async function fatalError(error) {
  const message = String(error?.message || error || 'Erro desconhecido').slice(0, 1000)
  logger.error({ err: error }, 'Erro no bridge WhatsApp')
  connected = false
  await writeState({
    status: 'ERROR',
    connected: false,
    message,
    error_code: 'BAILEYS_ERROR',
  })
}

async function internalPost(endpoint, body = null) {
  const response = await fetch(`${INTERNAL_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${BRIDGE_TOKEN}`,
      'Content-Type': 'application/json',
      'X-WhatsApp-Bridge': 'baileys-node',
    },
    body: body === null ? '{}' : JSON.stringify(body),
    signal: AbortSignal.timeout(12000),
  })
  if (response.status === 204) return null
  const text = await response.text()
  let payload = null
  try { payload = text ? JSON.parse(text) : null } catch {}
  if (!response.ok) {
    throw new Error(payload?.error || `Django respondeu HTTP ${response.status}`)
  }
  return payload
}

function normalizeDigits(phone) {
  let digits = String(phone || '').replace(/\D+/g, '')
  if (digits.startsWith('00')) digits = digits.slice(2)
  if (digits.length === 10 || digits.length === 11) digits = `55${digits}`
  return digits
}

function toJid(phone) {
  const digits = normalizeDigits(phone)
  if (digits.length < 10 || digits.length > 15) throw new Error('Número de WhatsApp inválido')
  return `${digits}@s.whatsapp.net`
}

function brazilianCandidates(phone, provided = []) {
  const base = [normalizeDigits(phone), ...provided.map(normalizeDigits)].filter(Boolean)
  const first = base[0] || ''
  if (first.startsWith('55')) {
    const national = first.slice(2)
    if (national.length === 11 && national.slice(2, 3) === '9') {
      base.push(`55${national.slice(0, 2)}${national.slice(3)}`)
    } else if (national.length === 10) {
      base.push(`55${national.slice(0, 2)}9${national.slice(2)}`)
    }
  }
  return [...new Set(base)].filter(d => d.length >= 10 && d.length <= 15)
}

async function resolveWhatsAppRecipient(phone, provided = []) {
  const candidates = brazilianCandidates(phone, provided)
  if (!candidates.length) throw new Error('Número de WhatsApp inválido')
  if (typeof socket?.onWhatsApp === 'function') {
    for (const candidate of candidates) {
      for (const query of [candidate, toJid(candidate)]) {
        try {
          const result = await socket.onWhatsApp(query)
          const match = Array.isArray(result) ? result.find(item => item?.exists && item?.jid) : null
          if (match?.jid) {
            return { jid: String(match.jid), phone: candidate }
          }
        } catch (error) {
          logger.debug({ err: error, candidate }, 'Consulta onWhatsApp falhou para candidato')
        }
      }
    }
    throw new Error(`WhatsApp não encontrou o número cadastrado. Testados: ${candidates.join(', ')}`)
  }
  return { jid: toJid(candidates[0]), phone: candidates[0] }
}


async function pollQueue() {
  if (stopping || !connected || !socket || queueBusy) return
  queueBusy = true
  let job = null
  try {
    job = await internalPost('/whatsapp/internal/claim/')
    if (!job) return
    const recipient = await resolveWhatsAppRecipient(job.phone, Array.isArray(job.phone_candidates) ? job.phone_candidates : [])
    await socket.sendMessage(recipient.jid, { text: String(job.body || '') })
    await internalPost(`/whatsapp/internal/result/${job.id}/`, { ok: true, resolved_phone: recipient.phone })
    await new Promise(resolve => setTimeout(resolve, SEND_DELAY_MS))
    await writeState({
      status: 'CONNECTED',
      connected: true,
      message: 'WhatsApp conectado e pronto para enviar.',
      last_message_id: job.id,
      last_message_at: nowIso(),
    })
  } catch (error) {
    logger.warn({ err: error, jobId: job?.id }, 'Falha no envio/fila')
    if (job?.id) {
      try {
        await internalPost(`/whatsapp/internal/result/${job.id}/`, {
          ok: false,
          error: String(error?.message || error || 'Falha no envio').slice(0, 1800),
        })
      } catch (reportError) {
        logger.warn({ err: reportError }, 'Falha ao devolver resultado para Django')
      }
    }
  } finally {
    queueBusy = false
  }
}

async function resetSession() {
  if (resetting) return
  resetting = true
  clearTimeout(reconnectTimer)
  connected = false
  try { await socket?.logout?.() } catch {}
  try { socket?.end?.(undefined) } catch {}
  try { socket?.ws?.close?.() } catch {}
  socket = null
  await removeQr()
  try { await fsp.rm(AUTH_DIR, { recursive: true, force: true }) } catch {}
  await fsp.mkdir(AUTH_DIR, { recursive: true })
  await writeState({
    status: 'STARTING',
    connected: false,
    message: 'Sessão removida. Gerando um novo QR Code…',
    error_code: '',
    account_jid: '',
    account_name: '',
  })
  connecting = false
  resetting = false
  await startSocket()
}

async function gracefulStop(reason = 'Serviço encerrado') {
  if (stopping) return
  stopping = true
  clearTimeout(reconnectTimer)
  try {
    await writeState({ status: 'STOPPING', connected: false, message: reason, online: true })
  } catch {}
  try { socket?.end?.(undefined) } catch {}
  try { socket?.ws?.close?.() } catch {}
  await removeQr()
  try {
    await writeState({
      status: 'OFFLINE',
      connected: false,
      online: false,
      pid: null,
      message: 'Serviço Baileys desligado.',
      qr_available: false,
    })
  } catch {}
  process.exit(0)
}

setInterval(async () => {
  try {
    if (fs.existsSync(RESET_FILE)) {
      try { await fsp.unlink(RESET_FILE) } catch {}
      await resetSession()
      return
    }
    if (fs.existsSync(STOP_FILE)) {
      try { await fsp.unlink(STOP_FILE) } catch {}
      await gracefulStop('Encerramento solicitado pelo Painel.')
      return
    }
    await writeState({ connected })
  } catch (error) {
    logger.warn({ err: error }, 'Falha no heartbeat')
  }
}, HEARTBEAT_MS).unref()

setInterval(() => {
  pollQueue().catch((error) => logger.warn({ err: error }, 'Falha no poll da fila'))
}, QUEUE_POLL_MS).unref()

process.on('SIGINT', () => gracefulStop('SIGINT recebido'))
process.on('SIGTERM', () => gracefulStop('SIGTERM recebido'))
process.on('uncaughtException', async (error) => {
  await fatalError(error)
  setTimeout(() => process.exit(1), 250).unref()
})
process.on('unhandledRejection', async (error) => {
  await fatalError(error)
})

await writeState({
  status: 'STARTING',
  connected: false,
  message: 'Iniciando serviço Baileys / Node.js…',
  started_at: nowIso(),
  pid: process.pid,
  backend: 'Baileys / Node.js',
  error_code: '',
})
await startSocket()
