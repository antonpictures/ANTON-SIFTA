import { open } from 'node:fs/promises'
import { homedir } from 'node:os'
import { scanZstdFrames, decompressZstdFrame } from '../packages/session/session-persistence-jsonl/src/zstd.ts'

const dir = `${homedir()}/.dsh/sessions/--Users-ioanganton-Music-ANTON_SIFTA--`
const ids = process.argv.slice(2)
for (const id of ids) {
  const f = `${dir}/${id}/session.jsonl.zstd`
  try {
    const h = await open(f)
    // read up to 64KB
    const c = Buffer.alloc(65536)
    const { bytesRead } = await h.read(c, 0, 65536, null)
    await h.close()
    const scan = scanZstdFrames(c.subarray(0, bytesRead), 1)
    const fr = scan.frames[0]
    if (!fr) { console.log(id, 'NO-FRAME torn@', scan.tornStart); continue }
    const plain = await decompressZstdFrame(c.subarray(fr.start, fr.end))
    const ok = plain[plain.length - 1] === 0x0a
    console.log(id, 'frame0', fr.start, '->', fr.end, 'plain', plain.length, 'newline-ok', ok, 'head', JSON.stringify(plain.subarray(0, 50).toString('utf8')))
  } catch (e) {
    console.log(id, 'ERR', String(e.message).slice(0, 90))
  }
}
