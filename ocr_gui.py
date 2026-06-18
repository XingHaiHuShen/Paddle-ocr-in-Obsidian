"""
简易可视化 OCR 工具 —— Tkinter 单文件桌面应用

用法：
    python ocr_gui.py

功能：
    - 拖拽图片到窗口 / 点按钮选图 / 直接 Ctrl+V 粘贴截图
    - 自动调用 PaddleOCR 云端 API（与方案.md 一致：/doc-parsing 端点）
    - 左侧预览原图（或布局检测图），右侧显示可编辑识别结果
    - 一键复制 / 保存 / 重试 / 清除

前置：
    1. 已安装 paddleocr（pip install paddleocr）
    2. 配置 Token（两种方式任选其一）：
       a) 环境变量（推荐 PowerShell 临时用）：
          $env:PADDLEOCR_ACCESS_TOKEN = "你的token"
       b) 启动后点右上角「⚙️ 配置 Token」按钮，填入后会保存到
          同目录的 .ocr_gui_config.json，下次启动自动生效
       优先级：环境变量 > 配置文件
"""

import base64
import json
import os
import re
import sys
import threading
import tkinter as tk
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from paddleocr import PaddleOCRClient
except ImportError:
    print("请先安装 paddleocr：pip install paddleocr")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────
TOKEN_ENV = "PADDLEOCR_ACCESS_TOKEN"
CONFIG_FILE = Path(__file__).parent / ".ocr_gui_config.json"
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".tif"}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# 后处理：HTML 表格 -> Markdown
# ─────────────────────────────────────────────────────────────
def trim_text(text: str) -> str:
    return re.sub(r"^\s+|\s+$", "", text or "")


def html_table_to_markdown(text: str) -> str:
    """把 PaddleOCR 返回的 <table>...</table> 转换成 Markdown 表格"""
    if "<table" not in text:
        return text

    def convert_one(table_html: str) -> str:
        # 抓所有 <tr>
        tr_blocks = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.S | re.I)
        if not tr_blocks:
            return table_html

        matrix = []
        for tr in tr_blocks:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.S | re.I)
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
            matrix.append(cells)

        if not matrix:
            return table_html
        max_cols = max(len(r) for r in matrix)
        for r in matrix:
            while len(r) < max_cols:
                r.append("")

        header = "| " + " | ".join(matrix[0]) + " |"
        sep = "| " + " | ".join(["---"] * max_cols) + " |"
        body = "\n".join("| " + " | ".join(r) + " |" for r in matrix[1:])
        return f"{header}\n{sep}\n{body}" if body else f"{header}\n{sep}"

    # 逐个替换（不区分大小写匹配标签）
    out = []
    last_end = 0
    for m in re.finditer(r"<table\b[^>]*>.*?</table>", text, flags=re.S | re.I):
        out.append(text[last_end:m.start()])
        out.append(convert_one(m.group(0)))
        last_end = m.end()
    out.append(text[last_end:])
    return "".join(out)


# ─────────────────────────────────────────────────────────────
# 主窗口
# ─────────────────────────────────────────────────────────────
class OCRApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🔍 PaddleOCR 文字识别（简易可视化）")
        self.root.geometry("1100x700")
        self.root.minsize(900, 560)

        # 状态
        self.cfg = load_config()
        # 优先用环境变量；否则用本地配置文件（设置过的话）
        env_token = os.environ.get(TOKEN_ENV, "").strip()
        file_token = (self.cfg.get("token") or "").strip()
        if env_token:
            self._active_token = env_token
            self._token_source = "env"
        elif file_token:
            self._active_token = file_token
            self._token_source = "file"
        else:
            self._active_token = ""
            self._token_source = None
        self.last_blob: bytes | None = None
        self.last_mime = "image/png"
        self.last_layout_url: str | None = None
        self.last_result_text: str = ""
        self.is_busy = False

        # 颜色 / 字体
        self.bg = "#f7f7fa"
        self.accent = "#1976d2"
        self.ok = "#2e7d32"
        self.err = "#c62828"
        self.font_text = ("Microsoft YaHei", 10)
        self.font_mono = ("Consolas", 10)

        self._build_ui()
        self._check_token()

    # ── UI ──────────────────────────────────────────────
    def _build_ui(self):
        self.root.configure(bg=self.bg)

        # 顶栏：标题 + Token 状态 + 配置入口
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="🔍 PaddleOCR 文字识别", font=("Microsoft YaHei", 14, "bold"),
                  background=self.bg).pack(side="left")
        ttk.Button(top, text="⚙️ 配置 Token", command=self._open_token_dialog).pack(side="right", padx=(6, 0))
        self.token_lbl = ttk.Label(top, text="", foreground=self.err, background=self.bg)
        self.token_lbl.pack(side="right")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=self.bg)
        style.configure("Card.TFrame", background="white", relief="flat")
        style.configure("TLabel", background=self.bg, font=self.font_text)
        style.configure("Card.TLabel", background="white", font=self.font_text)
        style.configure("Status.TLabel", background="#eceff1", font=self.font_text, padding=6)
        style.configure("TButton", font=self.font_text, padding=6)
        style.configure("Accent.TButton", font=self.font_text, padding=8)
        style.configure("TNotebook.Tab", font=self.font_text, padding=(12, 6))

        # 主体：左图 / 右文
        body = ttk.Frame(self.root, padding=(10, 4))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=5, uniform="cols")
        body.columnconfigure(1, weight=6, uniform="cols")
        body.rowconfigure(0, weight=1)

        # ── 左：图片预览 ──
        left = ttk.Frame(body, style="Card.TFrame", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        tabs = ttk.Notebook(left)
        tabs.grid(row=0, column=0, sticky="ew")

        # 「原图」Tab
        tab_orig = ttk.Frame(tabs, style="Card.TFrame")
        tabs.add(tab_orig, text="原图")
        self.canvas = tk.Canvas(tab_orig, bg="white", highlightthickness=1,
                                highlightbackground="#cfd8dc")
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<Configure>", lambda e: self._redraw_preview())

        # 「布局检测图」Tab（OCR 后才有）
        self.tab_layout = ttk.Frame(tabs, style="Card.TFrame")
        self.canvas_layout = tk.Canvas(self.tab_layout, bg="white", highlightthickness=1,
                                       highlightbackground="#cfd8dc")
        self.canvas_layout.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas_layout.bind("<Configure>", lambda e: self._redraw_layout())

        # 占位提示
        self.hint = tk.Label(self.canvas, text="拖拽图片到此处\n或 Ctrl+V 粘贴截图\n或点下方「选择图片」",
                             bg="white", fg="#90a4ae", font=("Microsoft YaHei", 12),
                             justify="center")
        self.canvas.create_window(0, 0, window=self.hint, anchor="center", tags="hint")
        self.canvas.bind("<Button-1>", lambda e: self._choose_file())

        # 左下：按钮 + 拖放提示
        left_btns = ttk.Frame(left)
        left_btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        left_btns.columnconfigure(0, weight=1)
        ttk.Button(left_btns, text="📂 选择图片", command=self._choose_file).grid(row=0, column=0, sticky="ew")

        # ── 右：结果 ──
        right = ttk.Frame(body, style="Card.TFrame", padding=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Tab 切换 markdown / html（识别成功后才有意义）
        res_tabs = ttk.Notebook(right)
        res_tabs.grid(row=0, column=0, sticky="ew")
        self.tab_md = ttk.Frame(res_tabs, style="Card.TFrame")
        self.tab_html = ttk.Frame(res_tabs, style="Card.TFrame")
        res_tabs.add(self.tab_md, text="Markdown 表格")
        res_tabs.add(self.tab_html, text="HTML（原始）")

        self.txt_md = tk.Text(self.tab_md, wrap="word", font=self.font_mono,
                              relief="flat", padx=8, pady=8, undo=True)
        self.txt_html = tk.Text(self.tab_html, wrap="word", font=self.font_mono,
                                relief="flat", padx=8, pady=8, undo=True)
        for w in (self.txt_md, self.txt_html):
            sb = ttk.Scrollbar(w.master, orient="vertical", command=w.yview)
            w.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            w.pack(side="left", fill="both", expand=True)

        # 操作按钮
        btns = ttk.Frame(right)
        btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for i in range(4):
            btns.columnconfigure(i, weight=1)
        ttk.Button(btns, text="📋 复制", command=self._copy).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(btns, text="💾 保存为 .md", command=self._save).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(btns, text="🔄 重试", command=self._retry).grid(row=0, column=2, sticky="ew", padx=2)
        ttk.Button(btns, text="🗑️ 清除", command=self._clear).grid(row=0, column=3, sticky="ew", padx=2)

        # 状态栏
        self.status = ttk.Label(self.root, text="就绪", style="Status.TLabel", anchor="w")
        self.status.pack(fill="x", side="bottom")

        # 拖拽支持
        self._setup_dnd()

        # 全局 Ctrl+V 监听
        self.root.bind_all("<Control-v>", self._on_paste)

    def _setup_dnd(self):
        # Tkinter 原生不支持拖放，用 windnd 占位提示（若未安装则仅提示）
        try:
            from tkinterdnd2 import DND_FILES  # noqa
            # 如果装了 tkinterdnd2 就启用
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            # 没装也不影响主要功能，提示一下
            self.canvas.bind("<Button-1>", lambda e: self._choose_file())

    # ── Token ───────────────────────────────────────────
    def _check_token(self):
        if self._active_token:
            where = "环境变量" if self._token_source == "env" else f"配置文件 {CONFIG_FILE.name}"
            masked = self._active_token[:4] + "…" + self._active_token[-4:] if len(self._active_token) > 12 else "****"
            self.token_lbl.config(text=f"✓ Token 已就绪（{where}：{masked}）", foreground=self.ok)
        else:
            self.token_lbl.config(text=f"⚠ 未配置 Token（点右上角「⚙️ 配置 Token」）", foreground=self.err)
            self._set_status("⚠ 请先配置 Token（点右上角「⚙️ 配置 Token」按钮）", err=True)

    def _open_token_dialog(self):
        """弹窗让用户填写 / 覆盖 token，并保存到本地配置文件"""
        dlg = tk.Toplevel(self.root)
        dlg.title("配置 Token")
        dlg.geometry("520x260")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        frm = ttk.Frame(dlg, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="PaddleOCR Access Token",
                  font=("Microsoft YaHei", 11, "bold")).pack(anchor="w")
        ttk.Label(frm, text=f"将保存到本地配置文件：{CONFIG_FILE}",
                  foreground="#607d8b").pack(anchor="w", pady=(2, 8))

        # 显示/隐藏切换
        show_var = tk.BooleanVar(value=False)
        token_var = tk.StringVar(value=self.cfg.get("token", ""))
        entry = ttk.Entry(frm, textvariable=token_var, show="•", width=60, font=self.font_mono)
        entry.pack(fill="x", pady=(0, 6))
        entry.focus_set()

        def toggle():
            entry.config(show="" if show_var.get() else "•")
        ttk.Checkbutton(frm, text="显示明文", variable=show_var, command=toggle).pack(anchor="w")

        # 环境变量优先级提示
        env_token = os.environ.get(TOKEN_ENV, "").strip()
        if env_token:
            ttk.Label(frm, text=f"⚠ 已设置环境变量 {TOKEN_ENV}，将优先使用环境变量",
                      foreground="#e65100").pack(anchor="w", pady=(8, 0))

        # 按钮栏
        btn_bar = ttk.Frame(frm)
        btn_bar.pack(fill="x", pady=(16, 0))
        def save_and_close():
            new_token = token_var.get().strip()
            self.cfg["token"] = new_token
            save_config(self.cfg)
            # 重新评估激活 token
            env_now = os.environ.get(TOKEN_ENV, "").strip()
            if env_now:
                self._active_token = env_now
                self._token_source = "env"
            elif new_token:
                self._active_token = new_token
                self._token_source = "file"
            else:
                self._active_token = ""
                self._token_source = None
            self._check_token()
            dlg.destroy()

        def clear_token():
            token_var.set("")
            self.cfg.pop("token", None)
            save_config(self.cfg)
            self._active_token = ""
            self._token_source = None
            self._check_token()
            dlg.destroy()

        ttk.Button(btn_bar, text="保存", command=save_and_close).pack(side="right", padx=(6, 0))
        ttk.Button(btn_bar, text="清除已保存的 Token", command=clear_token).pack(side="left")
        ttk.Button(btn_bar, text="取消", command=dlg.destroy).pack(side="right")

    # ── 输入处理 ─────────────────────────────────────────
    def _on_paste(self, event=None):
        if self.is_busy:
            self._set_status("⏳ 正在识别，请稍候...", err=False, transient=False)
            return
        try:
            img = self.root.clipboard_get()  # 不一定是图片
        except tk.TclError:
            return
        # 剪贴板拿到的若是图像 PIL 表示（需要 pillow + ImageGrab）
        try:
            from PIL import ImageGrab, Image
            img_obj = ImageGrab.grab_clipboard()
            if isinstance(img_obj, Image.Image):
                buf = BytesIO()
                img_obj.save(buf, format="PNG")
                self._handle_image_bytes(buf.getvalue(), "image/png")
                return "break"
        except Exception:
            pass

    def _on_drop(self, event):
        if self.is_busy:
            self._set_status("⏳ 正在识别，请稍候...", err=False, transient=False)
            return
        files = event.data
        # tkinterdnd2 给的文件路径可能带花括号
        files = self.root.tk.splitlist(files)
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in SUPPORTED_EXT and Path(f).exists():
                self._handle_path(Path(f))
                break
        return "break"

    def _choose_file(self):
        if self.is_busy:
            return
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片", " ".join("*" + e for e in sorted(SUPPORTED_EXT))),
                       ("所有文件", "*.*")],
        )
        if path:
            self._handle_path(Path(path))

    def _handle_path(self, p: Path):
        try:
            data = p.read_bytes()
        except Exception as e:
            messagebox.showerror("读取失败", str(e))
            return
        ext = p.suffix.lower()
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/png")
        self._handle_image_bytes(data, mime)

    def _handle_image_bytes(self, data: bytes, mime: str = "image/png"):
        self.last_blob = data
        self.last_mime = mime
        self._show_image(data)
        self._run_ocr_async(data)

    # ── 图片预览 ─────────────────────────────────────────
    def _show_image(self, data: bytes):
        try:
            from PIL import Image, ImageTk
            self._pil_img = Image.open(BytesIO(data))
            self.canvas.delete("all")
            self._redraw_preview()
        except ImportError:
            messagebox.showerror("缺少依赖", "需要 Pillow：pip install pillow")
        except Exception as e:
            messagebox.showerror("图片错误", str(e))

    def _redraw_preview(self):
        if not hasattr(self, "_pil_img") or self._pil_img is None:
            return
        from PIL import ImageTk
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return
        img = self._pil_img.copy()
        img.thumbnail((cw - 8, ch - 8))
        self._tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._tk_img, anchor="center")

    def _redraw_layout(self):
        if not hasattr(self, "_layout_pil") or self._layout_pil is None:
            return
        from PIL import ImageTk
        cw = self.canvas_layout.winfo_width()
        ch = self.canvas_layout.winfo_height()
        if cw < 10 or ch < 10:
            return
        img = self._layout_pil.copy()
        img.thumbnail((cw - 8, ch - 8))
        self._tk_layout = ImageTk.PhotoImage(img)
        self.canvas_layout.delete("all")
        self.canvas_layout.create_image(cw // 2, ch // 2, image=self._tk_layout, anchor="center")

    # ── OCR 调用 ─────────────────────────────────────────
    def _run_ocr_async(self, data: bytes):
        token = self._active_token
        if not token:
            messagebox.showwarning("未配置 Token",
                                   "请先点右上角「⚙️ 配置 Token」设置，"
                                   "或在 PowerShell 中设置环境变量：\n\n"
                                   f"$env:{TOKEN_ENV} = \"你的token\"")
            return
        if self.is_busy:
            return
        self.is_busy = True
        self._set_status("🔍 正在识别...", err=False)

        def task():
            try:
                # 把 token 临时注入到环境变量，让 PaddleOCRClient 自动读取
                prev = os.environ.get(TOKEN_ENV)
                os.environ[TOKEN_ENV] = token
                try:
                    client = PaddleOCRClient()
                    try:
                        # 写入临时文件走 SDK（parse_document 支持 file_path）
                        import tempfile
                        suffix = ".png" if "png" in self.last_mime else ".jpg"
                        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                            tmp.write(data)
                            tmp_path = tmp.name
                        try:
                            result = client.parse_document(file_path=tmp_path)
                        finally:
                            try:
                                os.unlink(tmp_path)
                            except Exception:
                                pass
                    finally:
                        client.close()
                finally:
                    if prev is None:
                        os.environ.pop(TOKEN_ENV, None)
                    else:
                        os.environ[TOKEN_ENV] = prev

                texts = [trim_text(p.markdown_text) for p in result.pages if p.markdown_text]
                joined_md = "\n\n---\n\n".join(t for t in texts if t)
                md_text = html_table_to_markdown(joined_md) if joined_md else ""

                # HTML 原文（原始 markdownText 拼接）
                html_text = "\n\n---\n\n".join(texts)

                # 布局图 URL
                layout_url = None
                if result.pages and result.pages[0].output_images:
                    layout_url = result.pages[0].output_images.get("layout_det_res")

                self.root.after(0, self._on_ocr_done, md_text, html_text, layout_url)
            except Exception as e:
                err = str(e)
                # 脱敏
                if token:
                    err = err.replace(token, "[REDACTED]")
                self.root.after(0, self._on_ocr_error, err)

        threading.Thread(target=task, daemon=True).start()

    def _on_ocr_done(self, md_text: str, html_text: str, layout_url: str | None):
        self.is_busy = False
        self.last_result_text = md_text
        self.txt_md.delete("1.0", "end")
        self.txt_md.insert("1.0", md_text)
        self.txt_html.delete("1.0", "end")
        self.txt_html.insert("1.0", html_text)
        n = len(md_text)
        self._set_status(f"✅ 已识别 {n} 字符", err=False)
        # 布局图
        if layout_url:
            self.last_layout_url = layout_url
            threading.Thread(target=self._fetch_layout_async, args=(layout_url,), daemon=True).start()
        else:
            # 没有布局图，移除该 Tab
            try:
                # 不移除，保留一个提示
                pass
            except Exception:
                pass

    def _on_ocr_error(self, err: str):
        self.is_busy = False
        self._set_status(f"❌ 识别失败: {err}", err=True)
        messagebox.showerror("识别失败", err)

    def _fetch_layout_async(self, url: str):
        try:
            import requests
            from PIL import Image
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            self._layout_pil = Image.open(BytesIO(r.content))
            self.root.after(0, self._redraw_layout)
        except Exception as e:
            # 布局图加载失败不影响主流程
            pass

    # ── 按钮 ─────────────────────────────────────────────
    def _copy(self):
        text = self.txt_md.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("提示", "没有可复制的内容")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status("📋 已复制到剪贴板", err=False)

    def _save(self):
        text = self.txt_md.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("提示", "没有可保存的内容")
            return
        path = filedialog.asksaveasfilename(
            title="保存为 Markdown",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("文本", "*.txt"), ("所有", "*.*")],
            initialfile="ocr_result.md",
        )
        if path:
            Path(path).write_text(text, encoding="utf-8")
            self._set_status(f"💾 已保存到 {path}", err=False)

    def _retry(self):
        if self.last_blob:
            self._handle_image_bytes(self.last_blob, self.last_mime)

    def _clear(self):
        self.last_blob = None
        self.last_layout_url = None
        self.last_result_text = ""
        self._pil_img = None
        self._layout_pil = None
        self.canvas.delete("all")
        self.canvas_layout.delete("all")
        # 重新画占位提示
        self.canvas.create_window(0, 0, window=self.hint, anchor="center", tags="hint")
        self.txt_md.delete("1.0", "end")
        self.txt_html.delete("1.0", "end")
        self._set_status("就绪", err=False)

    # ── 状态栏 ───────────────────────────────────────────
    def _set_status(self, msg: str, err: bool = False, transient: bool = True):
        self.status.config(text=msg, foreground=self.err if err else "#37474f")


def main():
    root = tk.Tk()
    OCRApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
