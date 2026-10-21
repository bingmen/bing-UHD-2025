# bing-JSON-all.py
# github.com/shenjuexiao
# 20261021

# bing-JSON-all.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
根据 bing-JSON-{mkt}-{year}.json 数据
下载 UHD 高清图到 bing-UHD-{mkt}-{year}/ 目录
下载 320x240 缩略图到 bing-320-{mkt}-{year}/ 目录
图片命名：YYYYMMDD_title_UHD_{mkt}.jpg / YYYYMMDD_320_{mkt}.jpg
按照 {mkt}，生成 bing-UHD-{mkt}-{year}.md
"""

import os
import re
import json
import time
import glob
import datetime
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------- 配置 ----------------
MKTS = ["de-DE", "en-CA", "en-GB", "en-IN", "en-US",
        "fr-FR", "it-IT", "ja-JP", "zh-CN"]

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

TABLE_SEPARATOR = "| --- | --- | --- | --- | --- |"

BING_BASE = "https://www.bing.com"
THUMB_SUFFIX = "_320x240.jpg"
UHD_SUFFIX = "_UHD.jpg"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")
MAX_WORKERS = 8
RETRY = 3


# ---------------- 工具函数 ----------------
def sanitize_filename(name: str) -> str:
    """把 title 处理为安全文件名"""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "", name)
    name = re.sub(r"\s+", "-", name.strip())
    return name[:80] if name else "untitled"


def http_download(url: str, dest: str) -> bool:
    """下载 url 到 dest，带重试"""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    for attempt in range(1, RETRY + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp, \
                    open(dest, "wb") as f:
                f.write(resp.read())
            return True
        except Exception as e:
            print(f"[retry {attempt}/{RETRY}] {url} -> {e}")
            time.sleep(2 * attempt)
    return False


def build_urls(item: dict):
    """从 JSON item 构造 缩略图 与 UHD 的 URL"""
    base = item.get("urlbase", "")
    if not base:
        return None, None
    thumb_url = f"{BING_BASE}{base}{THUMB_SUFFIX}"
    uhd_url = f"{BING_BASE}{base}{UHD_SUFFIX}"
    return thumb_url, uhd_url


def format_date(enddate: str) -> str:
    """'20261020' -> '2026-10-20'"""
    try:
        return datetime.datetime.strptime(enddate, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return enddate


# ---------------- 主流程 ----------------
def process_mkt_year(mkt: str, year: str, json_path: str):
    """处理单个 mkt + year"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("data", [])
    print(f"[{mkt} {year}] 共 {len(items)} 条记录")

    uhd_dir = f"bing-UHD-{mkt}-{year}"
    thumb_dir = f"bing-320-{mkt}-{year}"
    os.makedirs(uhd_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)

    # 下载任务
    tasks = []  # (kind, url, dest)
    for item in items:
        sd = item.get("startdate", "")
        if not sd.startswith(year):
            continue
        title = sanitize_filename(item.get("title", ""))
        uhd_name = f"{sd}_{title}_UHD_{mkt}.jpg"
        thumb_name = f"{sd}_320_{mkt}.jpg"
        uhd_url, thumb_url = build_urls(item)
        # 注意：build_urls 返回 (thumb, uhd)
        thumb_url, uhd_url = build_urls(item)
        if thumb_url:
            tasks.append((thumb_url, os.path.join(thumb_dir, thumb_name)))
        if uhd_url:
            tasks.append((uhd_url, os.path.join(uhd_dir, uhd_name)))

    # 并行下载
    ok, fail = 0, 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(http_download, url, dest) for url, dest in tasks]
        for fut in as_completed(futures):
            if fut.result():
                ok += 1
            else:
                fail += 1
    print(f"[{mkt} {year}] 下载完成: 成功 {ok}, 失败 {fail}")

    # 生成 Markdown
    lines = []
    lines.append(f"# {H1[mkt]} – UHD - {mkt} - {year}")
    lines.append("")
    lines.append(f"> {LAST_UPDATED[mkt]}：{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append("")
    lines.append(TABLE_HEADERS[mkt])
    lines.append(TABLE_SEPARATOR)

    # 按 enddate 倒序
    sorted_items = sorted(
        [x for x in items if x.get("startdate", "").startswith(year)],
        key=lambda x: x.get("enddate", ""),
        reverse=True,
    )

    for item in sorted_items:
        sd = item.get("startdate", "")
        enddate_fmt = format_date(item.get("enddate", ""))
        title = item.get("title", "").replace("|", "\\|")
        copyright_ = item.get("copyright", "").replace("|", "\\|")

        title_slug = sanitize_filename(item.get("title", ""))
        uhd_file = f"{sd}_{title_slug}_UHD_{mkt}.jpg"
        thumb_file = f"{sd}_320_{mkt}.jpg"

        thumb_rel = f"bing-320-{mkt}-{year}/{thumb_file}"
        uhd_rel = f"bing-UHD-{mkt}-{year}/{uhd_file}"

        # 缩略图走 jsdelivr CDN
        cdn_thumb = (f"https://cdn.jsdelivr.net/gh/bingmen/bing-UHD-{year}"
                     f"@main/bing-320-{mkt}-{year}/{thumb_file}")

        row = (f"| {enddate_fmt} | {title} | {copyright_} | "
               f"[![{thumb_file}]({cdn_thumb})]({cdn_thumb}) | "
               f"[UHD]({uhd_rel}) |")
        lines.append(row)

    md_path = f"bing-UHD-{mkt}-{year}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[{mkt} {year}] 已生成 {md_path}")


def main():
    # 找到所有 bing-JSON-{mkt}-{year}.json
    pattern = re.compile(r"^bing-JSON-([A-Za-z]{2}-[A-Za-z]{2})-(\d{4})\.json$")
    found = []
    for path in glob.glob("bing-JSON-*-*.json"):
        m = pattern.match(os.path.basename(path))
        if not m:
            continue
        mkt, year = m.group(1), m.group(2)
        if mkt not in MKTS:
            print(f"跳过未知 mkt: {path}")
            continue
        found.append((mkt, year, path))

    if not found:
        print("未找到任何 bing-JSON-{mkt}-{year}.json 文件")
        return

    found.sort()
    for mkt, year, path in found:
        try:
            process_mkt_year(mkt, year, path)
        except Exception as e:
            print(f"[错误] 处理 {path} 失败: {e}")


if __name__ == "__main__":
    main()
