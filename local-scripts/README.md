# Local OCR Scripts

> 基于 PaddleOCR 云端 API 的本地 Python 工具集

## 📌 已可用

两个脚本均已实现并测试通过：

| 脚本 | 功能 | 适用场景 |
|---|---|---|
| [`ocr_gui.py`](./ocr_gui.py) | Tkinter 可视化 OCR 桌面应用 | 偶尔手动识别一张或多张图片 |
| [`watch_and_ocr.py`](./watch_and_ocr.py) | 监听截图文件夹，新截图自动 OCR 并写剪贴板 | 后台常驻，自动处理截图 |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install paddleocr pyperclip pillow
# 可选：支持拖拽
pip install tkinterdnd2
```

### 2. 设置 Token

**方式 A：环境变量（推荐，临时用）**

PowerShell：
```powershell
$env:PADDLEOCR_ACCESS_TOKEN = "你的token"
```

bash/zsh：
```bash
export PADDLEOCR_ACCESS_TOKEN="你的token"
```

**方式 B：配置文件（GUI 内置）**

启动 `ocr_gui.py` → 点右上角「⚙️ 配置 Token」按钮 → 填入后保存到 `.ocr_gui_config.json`。

> 优先级：**环境变量 > 配置文件**

### 3. 运行

```bash
# GUI 模式
python ocr_gui.py

# 后台监听模式（默认监听 ./screenshots/）
python watch_and_ocr.py

# 自定义监听目录
python watch_and_ocr.py --dir D:/Screenshots
```

## 🎯 功能特性

### `ocr_gui.py` — Tkinter GUI

- ✅ 拖拽图片到窗口 / 点按钮选图 / `Ctrl+V` 粘贴截图
- ✅ 自动调用 PaddleOCR `/doc-parsing` 端点
- ✅ 左侧预览原图（或布局检测图），右侧显示可编辑识别结果
- ✅ 一键复制 / 保存 / 重试 / 清除
- ✅ HTML 表格 → Markdown 表格自动转换
- ✅ 失败可重试，状态栏实时反馈

### `watch_and_ocr.py` — 后台监听

- ✅ 监听指定目录，发现新图片（`.png/.jpg/.bmp/...`）自动 OCR
- ✅ 识别结果自动写入剪贴板（无需手动复制）
- ✅ 已处理图片记录到 `.ocr_state.json`（最多 500 条），避免重复识别
- ✅ 适合 Windows 截图工具设置为自动保存到固定目录的用户

## 🔧 配置说明

### `ocr_gui.py` 配置

- **环境变量**：`PADDLEOCR_ACCESS_TOKEN`
- **配置文件**：`.ocr_gui_config.json`（自动生成，已 gitignore）
- **支持图片格式**：`.png .jpg .jpeg .bmp .gif .webp .tiff .tif`

### `watch_and_ocr.py` 配置

- **CLI 参数**：`--dir <path>` 指定监听目录
- **状态文件**：`.ocr_state.json`（自动生成，已 gitignore）

## 🔗 与 obsidian-plugin 的关系

两者**调用同一个 PaddleOCR `/doc-parsing` 接口**，是同一 API 的不同封装：

| 维度 | local-scripts | obsidian-plugin |
|---|---|---|
| 语言 | Python | TypeScript |
| 运行环境 | 本地 Python | Obsidian 渲染进程 |
| 跨域 | Python 直连无 CORS | 需走 Obsidian `requestUrl()` |
| 状态 | ✅ 可用 | ⏳ 设计稿（见 `../obsidian-plugin/方案.md`） |

如果你**不**用 Obsidian、只想在本地方便地 OCR 截图 → 用本目录即可。
如果你想在 Obsidian 内并排校对 → 等 `obsidian-plugin/` 实现。

## 🐛 常见问题

**Q: 提示 "请先安装 paddleocr"**
A: `pip install paddleocr`

**Q: GUI 启动后无法拖拽？**
A: 安装 `pip install tkinterdnd2`；未安装仍可通过按钮选图或 `Ctrl+V` 粘贴。

**Q: watch_and_ocr.py 不工作？**
A: 检查 token 是否设置；检查 `--dir` 目录是否存在且可读。

**Q: 403 错误？**
A: Token 无效或过期，到 [PaddleOCR 官网](https://aistudio.baidu.com/paddleocr/task) 重新获取。
