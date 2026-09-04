import fs from 'node:fs'
import path from 'node:path'

const base = path.resolve(process.env.PANEL_BASE_DIR || '/runtime')
const file = path.join(base, 'local_data', 'whatsapp', 'state.json')

try {
  const state = JSON.parse(fs.readFileSync(file, 'utf8'))
  const heartbeat = Date.parse(String(state.heartbeat || ''))
  if (!Number.isFinite(heartbeat)) process.exit(1)
  const ageMs = Date.now() - heartbeat
  if (ageMs > 30000) process.exit(1)
  if (state.online === false && state.status !== 'OFFLINE') process.exit(1)
  process.exit(0)
} catch {
  process.exit(1)
}
