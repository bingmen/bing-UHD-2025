# bing-JSON-all-0.0.1.yml
# github.com/shenjuexiao
# 20261022

# bing-JSON-all.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bing 每日壁纸 UHD 下载与 Markdown 生成脚本
根据 bing-JSON-{mkt}-{year}.json 数据下载 UHD 超清图与 320x240 缩略图，并生成 Markdown 索引。
数据不存在时只生成表头。
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------- 常量配置

H1 = {
    "de-DE": "Bing-Tägliches Hintergrundbild",
    "en-CA": "Bing Daily Wallpaper",
    "en-GB": "Bing Daily Wallpaper",
    "en-IN": "Bing Daily Wallpaper",
    "en-US": "Bing Daily Wallpaper",
    "fr-FR": "Fond d'écran quotidien Bing",
    "it-IT": "Sfondo giornaliero di Bing",
    "ja-JP": "Bing デイリー壁紙",
    "zh-CN": "Bing 每日壁纸",
}

LAST_UPDATED = {
    "de-DE": "Zuletzt aktualisiert",
    "en-CA": "Last updated",
    "en-GB": "Last updated",
    "en-IN": "Last updated",
    "en-US": "Last updated",
    "fr-FR": "Dernière mise à jour",
    "it-IT": "Ultimo aggiornamento",
    "ja-JP": "最終更新",
    "zh-CN": "最后更新",
}

TABLE_HEADERS = {
    "de-DE": "| Datum | Titel | Urheberrecht | Vorschaubild | UHD-Bild |",
    "en-CA": "| Date | Title | Copyright | Thumbnail | UHD image |",
    "en-GB": "| Date | Title | Copyright | Thumbnail | UHD image |",
    "en-IN": "| Date | Title | Copyright | Thumbnail | UHD image |",
    "en-US": "| Date | Title | Copyright | Thumbnail | UHD image |",
    "fr-FR": "| Date | Titre | Droits d'auteur | Vignette | Image UHD |",
    "it-IT": "| Data | Titolo | Copyright | Miniatura | Immagine UHD |",
    "ja-JP": "| 日付 | タイトル | 著作権 | サムネイル | UHD 画像 |",
    "zh-CN": "| 日期 | 标题 | 版权 | 缩略图 | UHD 图像 |",
}

TABLE_SEPARATOR = "| :---: | :---: | :---: | :---: | :---: |"

BING_BASE = "https://www.bing.com"
CDN_BASE = "https://cdn.jsdelivr.net/gh/bingmen/bing-UHD-{year}@main"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

SUPPORTED_MKTS = [
    "de-DE", "en-CA", "en-GB", "en-IN", "en-US",
    "fr-FR", "it-IT", "ja-JP", "zh-CN",
]

# ---------------------------------------------------------------- 工具函数

def sanitize_title(title: str) -> str:
    """将标题转换为适合文件名的形式：去掉非法字符、空格转下划线。"""
    if not title:
        return "untitled"
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "", title)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "untitled"


def escape_md_cell(text: str) -> str:
    """转义 Markdown 表格单元格中的竖线。"""
    if text is None:
        return ""
    return str(text).replace("|", "\\|")


def format_date(enddate: str) -> str:
    """'YYYYMMDD' -> 'YYYY-MM-DD'"""
    if len(enddate) == 8 and enddate.isdigit():
        return f"{enddate[0:4]}-{enddate[4:6]}-{enddate[6:8]}"
    return enddate


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_image(url: str, dest: Path, retries: int = 3) -> bool:
    """下载图片到 dest，成功返回 True。已存在则跳过。"""
    if dest.exists() and dest.stat().st_size > 0:
        return True

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200 and resp.content:
                dest.write_bytes(resp.content)
                return True
            print(f"  [警告] 下载失败 (HTTP {resp.status_code})：{url}")
        except Exception as e:  # noqa: BLE001
            print(f"  [错误] 第 {attempt} 次下载异常：{url} ({e})")
        time.sleep(1.5 * attempt)

    return False


# ---------------------------------------------------------------- 主流程

def process_item(item: dict, mkt: str, year: str,
                 uhd_dir: Path, thumb_dir: Path):
    """处理单条 JSON 记录，返回 Markdown 行所需信息；全部下载失败返回 None。"""
    startdate = item.get("startdate", "")
    enddate = item.get("enddate", startdate)
    title = item.get("title", "")
    copyright_ = item.get("copyright", "")
    url_path = item.get("url", "")

    # 去掉查询参数后缀，得到纯 id 路径
    base_url_path = url_path.split("&")[0] if url_path else ""

    # 构造 UHD / 1920x1080 / 320x240 URL
    uhd_url = f"{BING_BASE}{base_url_path.replace('1920x1080.jpg', 'UHD.jpg')}"
    fallback_url = f"{BING_BASE}{base_url_path}"
    thumb_url = f"{BING_BASE}{base_url_path.replace('1920x1080.jpg', '320x240.jpg')}"

    safe_title = sanitize_title(title)

    # UHD 文件名（区分 UHD 与回退 1920x1080）
    uhd_name = f"{startdate}_{safe_title}_UHD_{mkt}.jpg"
    fallback_name = f"{startdate}_{safe_title}_1920x1080_{mkt}.jpg"
    thumb_name = f"{startdate}_320_{mkt}.jpg"

    uhd_dest = uhd_dir / uhd_name
    fallback_dest = uhd_dir / fallback_name
    thumb_dest = thumb_dir / thumb_name

    # 先尝试 UHD
    uhd_ok = download_image(uhd_url, uhd_dest)
    final_url = uhd_url
    final_name = uhd_name

    if not uhd_ok:
        print(f"  [回退] UHD 不存在，尝试 1920x1080：{startdate}")
        fallback_ok = download_image(fallback_url, fallback_dest)
        if fallback_ok:
            uhd_ok = True
            final_url = fallback_url
            final_name = fallback_name
        else:
            # 清理可能的空 UHD 文件
            if uhd_dest.exists() and uhd_dest.stat().st_size == 0:
                uhd_dest.unlink(missing_ok=True)
            print(f"  [跳过] UHD 与 1920x1080 均无法下载：{startdate}")

    # 下载缩略图
    thumb_ok = download_image(thumb_url, thumb_dest)
    if not thumb_ok:
        print(f"  [跳过] 缩略图无法下载：{startdate}")

    # 仅当缩略图与（UHD/回退）至少有一个成功时，才写入 Markdown
    if not uhd_ok and not thumb_ok:
        return None

    date_display = format_date(enddate)

    # 缩略图 CDN 链接
    cdn_thumb = f"{CDN_BASE.format(year=year)}/bing-320-{mkt}-{year}/{thumb_name}"

    # UHD 列：链接文字固定为 "UHD"，指向实际下载成功的 UHD 或回退地址
    uhd_link = final_url

    return {
        "startdate": startdate,
        "date_display": date_display,
        "title": title,
        "copyright": copyright_,
        "cdn_thumb": cdn_thumb,
        "uhd_link": uhd_link,
        "final_name": final_name,
    }


def write_markdown(mkt: str, year: str, out_root: Path, results: list) -> Path:
    """生成 Markdown 文件（全量重建）。"""
    md_lines = []
    md_lines.append(f"# {H1[mkt]} - UHD - {mkt} - {year}")
    md_lines.append("")
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    md_lines.append(f"> {LAST_UPDATED[mkt]}：{utc_now} UTC")
    md_lines.append("")
    md_lines.append(TABLE_HEADERS[mkt])
    md_lines.append(TABLE_SEPARATOR)

    for r in results:
        md_lines.append(
            f"| {escape_md_cell(r['date_display'])} "
            f"| {escape_md_cell(r['title'])} "
            f"| {escape_md_cell(r['copyright'])} "
            f"| ![title]({r['cdn_thumb']}) "
            f"| [UHD]({r['uhd_link']}) |"
        )

    md_path = out_root / f"bing-UHD-{mkt}-{year}.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bing 每日壁纸 UHD 下载与 Markdown 生成"
    )
    parser.add_argument("--mkt", required=True, choices=SUPPORTED_MKTS,
                        help="市场，例如 zh-CN")
    parser.add_argument("--year", required=True,
                        help="年份，例如 2025")
    parser.add_argument("--json-file", default=None,
                        help="可选：指定 JSON 文件路径，默认为 bing-JSON-{mkt}-{year}.json")
    parser.add_argument("--out-dir", default=".",
                        help="可选：输出根目录，默认为当前目录")
    args = parser.parse_args()

    mkt = args.mkt
    year = args.year
    out_root = Path(args.out_dir).resolve()

    json_file = Path(args.json_file) if args.json_file else (
        out_root / f"bing-JSON-{mkt}-{year}.json"
    )

    # 目录
    uhd_dir = out_root / f"bing-UHD-{mkt}-{year}"
    thumb_dir = out_root / f"bing-320-{mkt}-{year}"

    # ---- 读取 JSON；不存在或为空则只生成表头 ----
    data = []
    if json_file.exists():
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                data = loaded
                print(f"[信息] 已加载 {len(data)} 条记录：{json_file}")
            else:
                print(f"[警告] JSON 根节点不是数组，按空数据处理：{json_file}")
        except Exception as e:  # noqa: BLE001
            print(f"[警告] JSON 解析失败，按空数据处理：{json_file} ({e})")
    else:
        print(f"[信息] JSON 文件不存在，仅生成表头：{json_file}")

    ensure_dir(uhd_dir)
    ensure_dir(thumb_dir)

    results = []
    for idx, item in enumerate(data, 1):
        startdate = item.get("startdate", "")
        title = item.get("title", "")
        print(f"[{idx}/{len(data)}] {startdate} - {title}")
        try:
            row = process_item(item, mkt, year, uhd_dir, thumb_dir)
        except Exception as e:  # noqa: BLE001
            print(f"  [错误] 处理失败：{e}")
            continue
        if row:
            results.append(row)

    # 按 startdate 倒序
    results.sort(key=lambda r: r["startdate"], reverse=True)

    md_path = write_markdown(mkt, year, out_root, results)
    print(f"[完成] Markdown 已写入：{md_path}")
    print(f"[完成] UHD 图片目录：{uhd_dir}")
    print(f"[完成] 缩略图目录：{thumb_dir}")
    print(f"[完成] 条目数：{len(results)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
