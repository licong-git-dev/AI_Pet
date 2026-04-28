# PetPal Wrapped 录像工具

把月报 stories 录成 7-13 秒的官网 hero 视频。

## 一次性环境

```bash
# 装 Playwright + chromium 浏览器
cd tools/wrapped_video
npm install
npx playwright install chromium

# 系统层装 ffmpeg（Mac: brew install ffmpeg；Ubuntu: apt-get install ffmpeg）
ffmpeg -version
```

## 录制

```bash
# 在另一个终端把前端启起来
cd ../../frontend
npm run dev          # 或 npm run build && npm run preview

# 回来录
cd ../tools/wrapped_video
FRONTEND_URL=http://localhost:5173 node record.mjs
```

输出：`dist/wrapped-demo.mp4`（1080×1920 / yuv420p / faststart，可直接发微信、官网）

## 自定义

- 把 `record.mjs` 中 `VIEWPORT` 改成 `{1280, 720}` 即得到桌面横屏版。
- 想换成黄金主题色或不同 fixture 数据，改 `frontend/src/views/WrappedView.vue` 中的 `DEMO_FIXTURE`。
- 不需要 mp4，只要 webm？把 ffmpeg 步骤跳过，输出 `wrapped-demo.webm`（脚本会自动 fallback）。

## CI 集成

GitHub Actions 上放一段 ubuntu runner：
```yaml
- run: cd frontend && npm i && npm run build && npx vite preview --port 5173 &
- run: sleep 5
- run: cd tools/wrapped_video && npm i && npx playwright install --with-deps chromium
- run: cd tools/wrapped_video && FRONTEND_URL=http://localhost:5173 node record.mjs
- uses: actions/upload-artifact@v4
  with: { name: wrapped-demo, path: tools/wrapped_video/dist/* }
```
