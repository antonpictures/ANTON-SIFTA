import { open } from 'node:fs/promises'
import { homedir } from 'node:os'
import { execSync } from 'node:child_process'
// Use zstd CLI to tell us: 1 frame? window size? then dump raw bytes
const dir = `${homedir()}/.dsh/sessions/--Users-ioanganton-Music-ANTON_SIFTA--`
const id = 'session-18c84e55-5fa9-4527-8524-cf390b78ae2f'
const f = `${dir}/${id}/session.jsonl.zstd`
console.log(execSync(`zstd -lv '${f}' 2>&1 | head -8`).toString())
const h = await open(f)
const c = Buffer.alloc(64)
await h.read(c)
await h.close()
console.log('first 24 bytes:', c.subarray(0, 24).toString('hex'))
