# PetPal Frontend · Web Driver

最小可跑的 Vue 3 前端，用于：

- **分身房间**：订阅 `WSS /api/v1/ws?token=...` 上的 `channel: avatar_render` 事件，把 ASP 渲染成 CSS 兽体动画 + 气泡
- **画像月报**：拉取 `GET /api/v1/owner-profile/wrapped`，以 stories 方式翻看

## 开发

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

`vite.config.ts` 已配代理：`/api/*` 与 `/ws/*` → `localhost:8000`，
后端启动时直接连 dev server 即可。

## 构建

```bash
npm run build        # → frontend/dist
npm run preview
```

## 登录

页面要求粘贴一个有效的 JWT token（来自 `POST /api/v1/auth/login` 的
`access_token`），以及默认分身的 `pet_id`（用于"发送对话"按钮）。
token 仅存在浏览器 localStorage，无服务端会话。

## 接 Live2D

`<AvatarStage :live2d-model-url="...">` 传值时，CSS 兽体让位给具名插槽 `#live2d`，
父组件可在那里挂 [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display)
等任意 Live2D 渲染器，并消费同一份 `event` 数据（情绪、speech、animation 名）。

```vue
<AvatarStage :event="lastEvent" :live2d-model-url="'/models/cat.model3.json'">
  <template #live2d="{ event }">
    <MyLive2D :event="event" />
  </template>
</AvatarStage>
```

## 与三大支柱的对应关系

| 支柱 | 前端落点 |
| --- | --- |
| 长期记忆 | 后端在对话后写入；前端只展示对话回复（暂不直接读记忆库） |
| 主人画像 | `WrappedView` 拉取月报；`AvatarStage` 不感知 |
| 渲染适配层 | `useAvatarSocket` + `AvatarStage` 即 Web Driver 的本体 |
