#!/usr/bin/env node
/**
 * 一次性把 Live2D Cubism 官方免费示例模型 Hiyori 下载到 public/live2d/。
 * 文件较大（~6MB），不进 git，因此用此脚本按需获取。
 *
 * 用法：
 *   npm run fetch:live2d
 *
 * 来源：https://github.com/Live2D/CubismWebSamples（Cubism Sample 4 协议见仓库）
 * 仅做开发演示，正式商用请自行替换为授权模型。
 */
import { mkdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const TARGET = resolve(ROOT, 'public/live2d/hiyori')

const BASE = 'https://cdn.jsdelivr.net/gh/Live2D/CubismWebSamples@develop/Samples/Resources/Hiyori'

const FILES = [
  'Hiyori.model3.json',
  'Hiyori.physics3.json',
  'Hiyori.pose3.json',
  'Hiyori.cdi3.json',
  'Hiyori.4096/texture_00.png',
  'Hiyori.moc3',
  'motions/Hiyori_m01.motion3.json',
  'motions/Hiyori_m02.motion3.json',
  'motions/Hiyori_m03.motion3.json',
  'motions/Hiyori_m04.motion3.json',
  'motions/Hiyori_m05.motion3.json',
  'motions/Hiyori_m06.motion3.json',
  'motions/Hiyori_m07.motion3.json',
  'motions/Hiyori_m08.motion3.json',
  'motions/Hiyori_m09.motion3.json',
  'motions/Hiyori_m10.motion3.json',
  'expressions/F01.exp3.json',
  'expressions/F02.exp3.json',
  'expressions/F03.exp3.json',
  'expressions/F04.exp3.json',
  'expressions/F05.exp3.json',
  'expressions/F06.exp3.json',
  'expressions/F07.exp3.json',
  'expressions/F08.exp3.json',
]

async function fetchBinary(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status} ${url}`)
  return Buffer.from(await r.arrayBuffer())
}

async function main() {
  if (existsSync(resolve(TARGET, 'Hiyori.model3.json'))) {
    console.log('[live2d] 模型已存在，跳过下载：', TARGET)
    return
  }
  await mkdir(TARGET, { recursive: true })
  await mkdir(resolve(TARGET, 'motions'), { recursive: true })
  await mkdir(resolve(TARGET, 'expressions'), { recursive: true })
  await mkdir(resolve(TARGET, 'Hiyori.4096'), { recursive: true })

  console.log(`[live2d] 下载到 ${TARGET}`)
  for (const f of FILES) {
    const url = `${BASE}/${f}`
    process.stdout.write(`  ↳ ${f} ... `)
    try {
      const buf = await fetchBinary(url)
      const out = resolve(TARGET, f)
      await mkdir(dirname(out), { recursive: true })
      await writeFile(out, buf)
      console.log(`${(buf.length / 1024).toFixed(1)}KB`)
    } catch (e) {
      console.log(`FAILED: ${e.message}`)
    }
  }
  console.log('[live2d] done')
  console.log('   modelUrl: /live2d/hiyori/Hiyori.model3.json')
}

main().catch((e) => {
  console.error('[live2d] FATAL', e)
  process.exit(1)
})
