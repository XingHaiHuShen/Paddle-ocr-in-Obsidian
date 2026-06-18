# Paddle OCR 工具集

本仓库包含两套并行的 PaddleOCR 封装方案，分别面向不同使用场景：

| 目录 | 形态 | 平台 | 状态 | 适用人群 |
|---|---|---|---|---|
| [`obsidian-plugin/`](./obsidian-plugin/) | TypeScript 插件设计稿（v0.2） | Obsidian 桌面端 | 设计阶段，未编码 | 在 Obsidian 内写笔记并频繁处理截图的作者 |
| [`local-scripts/`](./local-scripts/) | Python 桌面/CLI 工具 | Windows/macOS/Linux | ✅ 可用 | 需要快捷 OCR 但不依赖 Obsidian 的用户 |

`PaddleOCR/` 是上游官方仓库克隆（参考用，不参与构建）。

---

## 🔗 两套方案的关系

```
            ┌─────────────────────────────────────────────┐
            │        PaddleOCR 云端 API (/doc-parsing)      │
            └────────────────────┬────────────────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
        ┌─────────────────┐           ┌─────────────────┐
        │ obsidian-plugin │           │  local-scripts  │
        │ (浏览器渲染进程) │           │   (Python 进程) │
        └─────────────────┘           └─────────────────┘
            TypeScript / paste             Python / Tkinter
                事件                            / watch
```

- **共享契约**：调用相同的 `/doc-parsing` 端点，相同的 Base64 传输格式，相同的 `fileType=1` 图片参数
- **差异**：UI 框架、运行环境、用户交互方式完全不同——一个跑在 Electron，一个跑在 Python
- **互不依赖**：两个目录可独立运行；Obsidian 插件不依赖 Python，Python 脚本不依赖 Obsidian

### 选哪个？

- 你是 Obsidian 重度用户，希望"截图 → 侧边栏预览 → 可视化校对 → 一键复制"无缝衔接 → **看 [obsidian-plugin/方案.md](./obsidian-plugin/方案.md)**（设计稿，可据此实现）
- 你想要一个即开即用的本地 OCR 工具（GUI 或后台监听截图文件夹）→ **直接用 [local-scripts/](./local-scripts/)**

---

## 📂 目录结构

```
Paddle OCR/
├── README.md                     ← 本文件（总览）
├── .gitignore
├── obsidian-plugin/              ← Obsidian 插件（设计稿）
│   ├── README.md
│   └── 方案.md                   ← v0.2 技术方案（约 1100 行）
├── local-scripts/                ← 本地 Python 脚本（已可用）
│   ├── README.md
│   ├── ocr_gui.py                ← Tkinter 可视化 OCR
│   ├── watch_and_ocr.py          ← 截图文件夹自动监听
│   ├── .ocr_gui_config.json      ← GUI 配置（运行时生成）
│   ├── out.txt / err.txt         ← 运行日志
│   └── __pycache__/
└── PaddleOCR/                    ← 上游官方仓库（参考）
```

---

## 🚀 快速开始

### local-scripts（立即可用）

```bash
pip install paddleocr pyperclip pillow
$env:PADDLEOCR_ACCESS_TOKEN = "你的token"

# 启动 GUI
python local-scripts/ocr_gui.py

# 或：监听截图文件夹，新截图自动 OCR
python local-scripts/watch_and_ocr.py --dir D:/Screenshots
```

### obsidian-plugin（设计阶段）

阅读 [`obsidian-plugin/方案.md`](./obsidian-plugin/方案.md) 了解设计；按方案骨架实现后产物为 `main.js + manifest.json + styles.css`，复制到 `.obsidian/plugins/obsidian-ocr/` 即可加载。

---

## 📜 License

本仓库中除 `PaddleOCR/` 子目录外的内容遵循 Apache 2.0（与上游 PaddleOCR 一致）。
