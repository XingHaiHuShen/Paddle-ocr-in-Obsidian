# Obsidian OCR 插件

> 基于 PaddleOCR 云端 API 的 Obsidian 截图 OCR 侧边栏插件

## 📌 当前状态

**v0.2 设计稿**（已完善）。尚未开始编码实现。

详细技术方案见 [方案.md](./方案.md)（约 1100 行，覆盖架构 / API / UI / 性能优化 / 测试）。

## 🎯 设计目标

把现有的"截图 → OCR → 复制到剪贴板"流程嵌入 Obsidian **侧边栏**，与编辑器**并排显示**，实现"所见即所得"的可视化校对体验。

```
┌────────────┬─────────────────────┬───────────────┐
│  文件浏览  │   笔记编辑器（原文）  │  OCR 侧边栏   │
│            │                     │  ┌─────────┐  │
│            │  用户在此校对 OCR    │  │ 图片预览 │  │
│            │  识别结果            │  └─────────┘  │
│            │                     │  ┌─────────┐  │
│            │                     │  │ 输出框  │  │
│            │                     │  │ (可编辑) │  │
│            │                     │  └─────────┘  │
└────────────┴─────────────────────┴───────────────┘
```

## 🔑 核心特性

| 特性 | 说明 |
|---|---|
| 截图 → OCR → 校对 → 复制，一气呵成 | 截图后 `Ctrl+Shift+O` 打开侧边栏，`Ctrl+V` 粘贴即可识别 |
| 与编辑器并排校对 | OCR 面板常驻，原文与识别结果左右对照 |
| 自动 HTML 表格 → Markdown 转换 | 后处理模块 `postprocess.htmlTableToMarkdown` |
| 布局检测图切换 | 响应中的 `layout_det_res` 可一键切换预览 |
| 零第三方依赖 | 仅用 Obsidian API + 浏览器内置 Web API |
| CORS 安全调用 | 用 Obsidian `requestUrl()` 走主进程，绕过 CORS |

## 🛠️ 技术栈

- **TypeScript** + esbuild
- **Obsidian Plugin API**（`ItemView`、`registerView`、`requestUrl`、`addSettingTab`）
- **浏览器内置**：`FileReader`、`navigator.clipboard`、`DOMParser`、`URL.createObjectURL`

## 📂 计划的项目结构（实现后）

```
obsidian-plugin/
├── manifest.json              # 插件清单
├── main.ts                    # 入口：注册视图 + 命令 + 设置
├── src/
│   ├── OCRView.ts             # 侧边栏 ItemView
│   ├── OCREngine.ts           # 引擎抽象接口
│   ├── engines/
│   │   ├── PaddleAPIEngine.ts # 云端 API 引擎（当前实现）
│   │   └── LocalDockerEngine.ts # 本地 Docker 引擎（预留）
│   ├── postprocess.ts         # 后处理：HTML→MD、trim、错误脱敏
│   ├── i18n.ts                # UI 文案常量
│   └── settings.ts            # 设置面板
├── styles.css                 # 侧边栏样式
├── package.json
├── tsconfig.json
└── esbuild.config.mjs
```

## 🚀 实现路线

参见 [方案.md §10 工作量估算](./方案.md#十工作量估算)（约 14-16 小时，3-4 天完成）。

**实现要点（避免常见坑）**：

1. **必须用 `requestUrl()` 而非 `fetch()`**：插件渲染进程 `fetch` 跨域会被 CORS 拦截
2. **快捷键用 `Mod` 而非 `Ctrl`**：Win/Linux 映射为 Ctrl，macOS 映射为 Cmd
3. **设置项变更要立即生效**：引擎实例持 `settings` 引用而非拷贝值
4. **`outputArea` 用 `<textarea>` 而非 `<div contenteditable>`**：简单稳定，光标不跳

## 🧪 与 local-scripts 的对比

| 维度 | obsidian-plugin | local-scripts |
|---|---|---|
| 语言 | TypeScript | Python |
| 运行环境 | Obsidian 渲染进程 | 本地 Python |
| UI 框架 | DOM（CSS 样式） | Tkinter |
| 用户操作 | 浏览器 paste 事件 | Tkinter 拖拽 + pyperclip |
| API 调用 | Obsidian `requestUrl()` | `requests`（直连，无 CORS） |
| 适用场景 | 在 Obsidian 内整理笔记 | 通用桌面 / 后台监听 |

两者调用的**是同一个 PaddleOCR `/doc-parsing` 接口**，共享请求/响应契约。
