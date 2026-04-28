#!/usr/bin/env node
/**
 * 用 Playwright 启 chromium，去前端 dev server / preview 的 /wrapped?demo=1 页面，
 * 录一段 webm，再用 ffmpeg 转成 mp4 放在 dist/。
 *
 * 前置条件：
 *   1. 前端 dev server 已启动（npm run dev / preview）
 *   2. 已经 `npm install` 装好 playwright（脚本会自动 install browsers）
 *   3. 系统装了 ffmpeg
 *
 * 用法：
 *   cd tools/wrapped_video
 *   npm install
 *   npx playwright install chromium
 *   FRONTEND_URL=http://localhost:5173 node record.mjs
 *
 * 输出：dist/wrapped-demo.mp4（移动端 9:16 / 1080x1920，约 13 秒）
 */
import { chromium } from 'playwright'
import { mkdir, rm, readdir, rename } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, resolve, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname)
const DIST = resolve(ROOT, 'dist')
const TMP = resolve(ROOT, 'tmp')

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5173'
const TARGET_PATH = '/wrapped?demo=1'

// 移动端视口（9:16）
const VIEWPORT = { width: 414, height: 896 }
const VIDEO_SIZE = { width: 1080, height: 1920 }

async function main() {
  await mkdir(DIST, { recursive: true })
  if (existsSync(TMP)) await rm(TMP, { recursive: true, force: true })
  await mkdir(TMP, { recursive: true })

  console.log('[wrapped-video] launching chromium...')
  const browser = await chromium.launch({ headless: true })

  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 2,
    recordVideo: {
      dir: TMP,
      size: VIDEO_SIZE,
    },
  })
  const page = await context.newPage()

  console.log(`[wrapped-video] open ${FRONTEND_URL}${TARGET_PATH}`)
  await page.goto(`${FRONTEND_URL}${TARGET_PATH}`, { waitUntil: 'networkidle' })

  // 等到 stories 自动播放完毕（最长 20 秒兜底）
  console.log('[wrapped-video] waiting for stories to complete...')
  try {
    await page.waitForFunction(
      () => document.querySelector('.wrapped')?.getAttribute('data-state') === 'complete',
      null,
      { timeout: 20000 },
    )
  } catch {
    console.warn('[wrapped-video] timeout waiting for completion; capturing what we have')
  }
  // 多停 1 秒让 closing 卡有展示时间
  await page.waitForTimeout(1200)

  console.log('[wrapped-video] closing context (flush video)...')
  await context.close()
  await browser.close()

  // 找到刚生成的 webm
  const files = await readdir(TMP)
  const webm = files.find((f) => f.endsWith('.webm'))
  if (!webm) {
    console.error('[wrapped-video] no webm produced')
    process.exit(2)
  }
  const webmPath = resolve(TMP, webm)
  const outMp4 = resolve(DIST, 'wrapped-demo.mp4')

  if (await hasFfmpeg()) {
    console.log('[wrapped-video] transcoding webm -> mp4 with ffmpeg...')
    await runFfmpeg(['-y', '-i', webmPath, '-c:v', 'libx264', '-preset', 'veryfast',
      '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', outMp4])
    console.log('[wrapped-video] done →', outMp4)
  } else {
    const fallback = resolve(DIST, 'wrapped-demo.webm')
    await rename(webmPath, fallback)
    console.warn('[wrapped-video] ffmpeg 未安装，跳过 mp4 转码 →', fallback)
  }

  await rm(TMP, { recursive: true, force: true })
}

function hasFfmpeg() {
  return new Promise((resolve) => {
    const p = spawn('ffmpeg', ['-version'])
    p.on('error', () => resolve(false))
    p.on('exit', (code) => resolve(code === 0))
  })
}

function runFfmpeg(args) {
  return new Promise((resolveOk, rejectErr) => {
    const p = spawn('ffmpeg', args, { stdio: 'inherit' })
    p.on('exit', (code) => (code === 0 ? resolveOk() : rejectErr(new Error('ffmpeg failed: ' + code))))
  })
}

main().catch((e) => {
  console.error('[wrapped-video] FATAL', e)
  process.exit(1)
})
