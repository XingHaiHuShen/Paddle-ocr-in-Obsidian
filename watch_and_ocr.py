"""
截图自动 OCR 工具——监听截图文件夹，新截图自动识别并写入剪贴板

用法：
    python watch_and_ocr.py
    python watch_and_ocr.py --dir D:\Screenshots

前置条件：
    1. paddleocr 已安装：pip install paddleocr
    2. 已设置 token：$env:PADDLEOCR_ACCESS_TOKEN = "你的token"
    3. 已安装剪贴板支持：pip install pyperclip
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import pyperclip
except ImportError:
    print("请先安装 pyperclip：pip install pyperclip")
    sys.exit(1)

from paddleocr import PaddleOCRClient


# ── 剪贴板 = 直接存文字的“文件” ──
# 以下配置告诉 Windows 哪些图片已处理过
STATE_FILE = Path(__file__).parent / ".ocr_state.json"


def load_state() -> set[str]:
    """加载已处理文件记录"""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return set(data.get("processed", []))
        except Exception:
            pass
    return set()


def save_state(processed: set[str]):
    """保存已处理文件记录（只保留最近 500 条，防膨胀）"""
    items = list(processed)[-500:]
    STATE_FILE.write_text(
        json.dumps({"processed": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".tif"}


def find_new_images(watch_dir: Path, processed: set[str]) -> list[Path]:
    """找出目录中尚未处理过的图片"""
    new_files = []
    for f in sorted(watch_dir.iterdir()):
        if f.suffix.lower() in SUPPORTED_EXT and str(f.absolute()) not in processed:
            new_files.append(f)
    return new_files


def ocr_image(client: PaddleOCRClient, image_path: Path) -> str:
    """调用 PaddleOCR API 解析图片，返回 Markdown 文本"""
    print(f"  🔍 识别中：{image_path.name} ...", end=" ", flush=True)
    try:
        result = client.parse_document(file_path=str(image_path.absolute()))
        texts = []
        for page in result.pages:
            if page.markdown_text:
                texts.append(page.markdown_text)
        text = "\n\n".join(texts)
        print(f"✓ ({len(text)} 字符)")
        return text
    except Exception as e:
        print(f"✗ 失败：{e}")
        return ""


def main():
    parser = argparse.ArgumentParser(description="截图自动 OCR - 新截图自动识别并写入剪贴板")
    parser.add_argument(
        "--dir",
        default=None,
        help="要监听的截图文件夹（默认：当前目录下的 screenshots 文件夹）",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="轮询间隔（秒），默认 2",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只处理现有图片一次，然后退出（不持续监听）",
    )
    args = parser.parse_args()

    # 确定监听目录
    if args.dir:
        watch_dir = Path(args.dir)
    else:
        watch_dir = Path(__file__).parent / "screenshots"

    watch_dir.mkdir(parents=True, exist_ok=True)

    # 检查 token
    token = os.environ.get("PADDLEOCR_ACCESS_TOKEN")
    if not token:
        print("❌ 请先设置环境变量 PADDLEOCR_ACCESS_TOKEN")
        print('   PowerShell: $env:PADDLEOCR_ACCESS_TOKEN = "a9dd51271c778d5ef0c0ba8eb6a322b5c699efa3"')
        sys.exit(1)

    # 初始化客户端
    client = PaddleOCRClient()
    processed = load_state()

    print(f"📁 监听目录：{watch_dir.absolute()}")
    print(f"🖼️  支持格式：{', '.join(SUPPORTED_EXT)}")
    print(f"⏱️  轮询间隔：{args.interval} 秒")
    print("─" * 50)

    if args.once:
        new_images = find_new_images(watch_dir, processed)
        if not new_images:
            print("没有新的图片需要处理。")
        for img in new_images:
            text = ocr_image(client, img)
            if text:
                pyperclip.copy(text)
                print(f"  📋 已复制到剪贴板！")
            processed.add(str(img.absolute()))
        save_state(processed)
        client.close()
        return

    try:
        print("🚀 开始监听... 把截图丢进上述文件夹即可自动识别。")
        print("   按 Ctrl+C 停止。")
        print("─" * 50)

        while True:
            new_images = find_new_images(watch_dir, processed)
            for img in new_images:
                text = ocr_image(client, img)
                if text:
                    pyperclip.copy(text)
                    print(f"  📋 已复制到剪贴板！")
                processed.add(str(img.absolute()))
                save_state(processed)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n👋 已停止监听。")
    finally:
        save_state(processed)
        client.close()


if __name__ == "__main__":
    main()
