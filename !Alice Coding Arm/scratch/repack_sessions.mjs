/**
 * Repack one-shot zstd session logs into the concatenated-frame container the
 * persistence contract expects: frame 0 = exactly one header line, then line
 * batches. Originals are backed up byte-exact before anything is replaced.
 */
import { open, mkdir, rename, readFile, writeFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { zstdDecompress } from 'node:zlib'
import { promisify } from 'node:util'
import { compressZstdFrame, scanZstdFrames, decompressZstdFrame } from '../packages/session/session-persistence-jsonl/src/zstd.ts'

const decompress = promisify(zstdDecompress)
const ROOT = join(homedir(), '.dsh', 'sessions')
const BACKUP = join(homedir(), '.dsh_backups', 'repack_2026-10-02')

const ids = process.argv.slice(2)
const dir = join(ROOT, '--Users-ioanganton-Music-ANTON_SIFTA--')

let okCount = 0
for (const id of ids) {
  const sdir = join(dir, id)
  const f = join(sdir, 'session.jsonl.zstd')
  const handle = await open(f)
  const raw = await handle.readFile()
  await handle.close()

  // Sanity: exactly one complete frame covering the whole file.
  const scan = scanZstdFrames(raw, 2)
  if (scan.frames.length !== 1 || scan.frames[0].start !== 0 || scan.frames[0].end !== raw.length) {
    console.log(`SKIP ${id}: not a single whole-file frame (${scan.frames.length} frames, torn=${scan.tornStart !== undefined})`)
    continue
  }

  const plaintext = await decompress(raw)
  const text = plaintext.toString('utf8')
  if (text.length === 0 || !text.endsWith('\n')) {
    console.log(`SKIP ${id}: plaintext is not newline-terminated`)
    continue
  }
  const lines = text.split('\n').slice(0, -1)
  const header = lines[0]
  if (!header.startsWith('{"type":"session"')) {
    console.log(`SKIP ${id}: first line is not the session header: ${header.slice(0, 60)}`)
    continue
  }

  // Backup byte-exact, then re-encode: frame 0 = header line; later frames = 500-line batches.
  const bdir = join(BACKUP, id)
  await mkdir(bdir, { recursive: true })
  await writeFile(join(bdir, 'session.jsonl.zstd.oneframe'), raw)

  const tmp = join(sdir, 'session.jsonl.zstd.repacked-tmp')
  const out = []
  out.push(await compressZstdFrame(Buffer.from(header + '\n', 'utf8')))
  for (let i = 1; i < lines.length; i += 500) {
    const batch = lines.slice(i, i + 500).join('\n') + '\n'
    out.push(await compressZstdFrame(Buffer.from(batch, 'utf8')))
  }
  await writeFile(tmp, Buffer.concat(out))
  await rename(tmp, f)

  // Verify: frame 0 must be exactly the header line, and full decode must match the original bytes.
  const verifyHandle = await open(f)
  const verifyRaw = await verifyHandle.readFile()
  await verifyHandle.close()
  const vscan = scanZstdFrames(verifyRaw, 2)
  const firstPlain = await decompressZstdFrame(verifyRaw.subarray(vscan.frames[0].start, vscan.frames[0].end))
  const whole = Buffer.concat(await Promise.all(
    vscan.frames.map(fr => decompressZstdFrame(verifyRaw.subarray(fr.start, fr.end)))
  ))
  const sameBytes = whole.equals(plaintext)
  const oneLine = firstPlain.length > 0 && firstPlain[firstPlain.length - 1] === 0x0a && !firstPlain.subarray(0, -1).includes(0x0a)
  console.log(`${sameBytes && oneLine ? 'REPACKED-OK' : 'REPACK-ERROR'} ${id}: frames=${vscan.frames.length} frame0=${firstPlain.length}b oneLine=${oneLine} bytesIdentical=${sameBytes}`)
  if (sameBytes && oneLine) okCount++
}
console.log(`done: ${okCount}/${ids.length} repacked clean`)
