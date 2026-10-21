# bing-JSON-all.py
# github.com/shenjuexiao
# 20261021

# bing-JSON-all.py
#!/usr/bin/env python3
"""Download Bing daily wallpapers (UHD + 320 thumbnails) and build Markdown tables."""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

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

SEP = "| --- | --- | --- | --- | --- |"

BING = "https://www.bing.com"
UHD_PARAMS = "&pid=hp&w=3840&h=2160&rs=1&c=4"
THUMB_PARAMS = "&pid=hp&w=320&h=240&rs=1&c=4"
CDN = "https://cdn.jsdelivr.net/gh/bingmen/bing-UHD-{year}@main"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (bing-JSON-all/1.0)"})


def slug(text: str, maxlen: int = 60) -> str:
    """Make a filesystem-safe slug from a title."""
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:maxlen] or "wallpaper"


def download(url: str, dest: Path, retries: int = 3) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip (exists): {dest.name}")
        return True
    for attempt in range(1, retries + 1):
        try:
            with SESSION.get(url, timeout=60, stream=True) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(65536):
                        f.write(chunk)
                tmp.replace(dest)
            print(f"  ok: {dest.name} ({dest.stat().st_size // 1024} KB)")
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt} failed for {dest.name}: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
    return False


def process(mkt: str, year: int, root: Path) -> None:
    json_path = root / f"bing-JSON-{mkt}-{year}.json"
    if not json_path.exists():
        print(f"[{mkt}] missing {json_path.name}, skipping")
        return

    data = json.loads(json_path.read_text(encoding="utf-8")).get("data", [])
    print(f"[{mkt}] {len(data)} entries")

    uhd_dir = root / f"bing-UHD-{mkt}-{year}"
    thumb_dir = root / f"bing-320-{mkt}-{year}"
    uhd_dir.mkdir(exist_ok=True)
    thumb_dir.mkdir(exist_ok=True)

    rows = []
    for item in data:
        start = item["startdate"]            # YYYYMMDD (image date)
        end = item["enddate"]                # YYYYMMDD (display date)
        ymd = start
        title = item.get("title", "")
        copyright_ = item.get("copyright", "")
        urlbase = item.get("urlbase", "")
        if not urlbase:
            continue

        uhd_name = f"{ymd}_{slug(title)}_UHD_{mkt}.jpg"
        thumb_name = f"{ymd}_320_{mkt}.jpg"

        download(BING + urlbase + UHD_PARAMS, uhd_dir / uhd_name)
        download(BING + urlbase + THUMB_PARAMS, thumb_dir / thumb_name)

        date_str = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
        thumb_url = f"{CDN.format(year=year)}/bing-320-{mkt}-{year}/{thumb_name}"
        uhd_url = f"{CDN.format(year=year)}/bing-UHD-{mkt}-{year}/{uhd_name}"

        rows.append((date_str, title, copyright_, thumb_url, uhd_url))

    # date descending (JSON is already descending, but enforce it)
    rows.sort(key=lambda r: r[0], reverse=True)

    md = []
    md.append(f"# {H1[mkt]} – UHD - {mkt} - {year}")
    md.append("")
    md.append(f"> {LAST_UPDATED[mkt]}：{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    md.append("")
    md.append(TABLE_HEADERS[mkt])
    md.append(SEP)
    for date_str, title, copyright_, thumb_url, uhd_url in rows:
        md.append(
            f"| {date_str} | {title} | {copyright_} "
            f"| ![{date_str}]({thumb_url}) | [UHD 高清图]({uhd_url}) |"
        )
    md.append("")

    out = root / f"bing-UHD-{mkt}-{year}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"[{mkt}] wrote {out.name} ({len(rows)} rows)")


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    years = [int(y) for y in sys.argv[2:]] or [2025]
    for year in years:
        for mkt in MKTS:
            process(mkt, year, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
