import { copyFile, mkdir, readdir, rename, rm } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const distRoot = resolve(projectRoot, 'dist')
const clientRoot = resolve(distRoot, 'client')
const serverRoot = resolve(distRoot, 'server')

await rm(clientRoot, { recursive: true, force: true })
await rm(serverRoot, { recursive: true, force: true })
await mkdir(clientRoot, { recursive: true })

for (const entry of await readdir(distRoot)) {
  if (entry === 'client' || entry === 'server' || entry === '.openai') continue
  await rename(resolve(distRoot, entry), resolve(clientRoot, entry))
}

await mkdir(serverRoot, { recursive: true })
await copyFile(resolve(projectRoot, 'sites', 'worker.mjs'), resolve(serverRoot, 'index.js'))
