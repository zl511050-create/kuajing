# -*- coding: utf-8 -*-
"""
FastMoss 墨西哥站点 Playwright 全自动无人值守巡航采集引擎 (旗舰版全量数据沉淀 + 拟人防风控变速巡航 + 极小内存微缩图)
支持模式：
1. --mode cruise (默认推荐) : 无人值守自动连续翻页巡航（拟人变速停留 5~10秒/页 + 每8页自动冷却休息 + S级潜力品详情页二级穿透）
2. --mode batch            : 指定页数快速巡检
3. --mode item             : @单品详情页全维度深度穿透抓取
4. --mode login            : 登录态验证
"""

import argparse
import base64
import datetime
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database.db_manager import init_db, upsert_product, log_scrape_task, get_product_by_id
from engine.taxonomy import classify_category, parse_fastmoss_product_cell_lines
from engine.es_translator import build_realistic_7d_series

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "browser_profile")
LIVE_STATUS_PATH = os.path.join(os.path.dirname(__file__), "live_status.json")
STOP_SIGNAL_PATH = os.path.join(os.path.dirname(__file__), "stop_signal.flag")
THUMBS_DIR = os.path.join(ROOT_DIR, "static", "thumbs")
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

def get_system_chrome_path() -> str:
    """自动探测不同操作系统下的本机正式版 Google Chrome 可执行文件路径"""
    if sys.platform == "darwin":
        p = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return p if os.path.exists(p) else ""
    elif sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return ""
    elif sys.platform.startswith("linux"):
        for p in ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"]:
            if os.path.exists(p):
                return p
        return ""
    return ""


def get_user_chrome_default_dir() -> str:
    """自动获取不同操作系统下 Chrome 用户数据 Default 目录"""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome/Default")
    elif sys.platform == "win32":
        return os.path.expandvars(r"%LocalAppData%\Google\Chrome\User Data\Default")
    else:
        return os.path.expanduser("~/.config/google-chrome/Default")


CHROME_SYSTEM_PATH = get_system_chrome_path()
CHROME_MAC_PATH = CHROME_SYSTEM_PATH  # 保持向下兼容

# FastMoss 旗舰版浏览器插件路径与固定 Extension ID
MOSS_EXT_PRIMARY_PATH = os.path.join(os.path.dirname(__file__), "extensions", "moss")
MOSS_EXT_FALLBACK_PATH = os.path.expanduser("~/Desktop/moss/moss")
MOSS_EXT_ID = "bhmemdccgceiofhgpagfieicgaabdgpl"
USER_CHROME_DEFAULT_DIR = get_user_chrome_default_dir()
# 旗舰版插件专用独立 profile（Playwright Chromium 内核，支持加载解包插件）
FLAGSHIP_PROFILE_DIR = os.path.join(os.path.dirname(__file__), "browser_profile_flagship")

FASTMOSS_URLS = {
    "new": "https://www.fastmoss.com/zh/e-commerce/newProducts?region=MX",
    "soaring": "https://www.fastmoss.com/zh/e-commerce/salinglist?region=MX",
    "hot": "https://www.fastmoss.com/zh/e-commerce/hotlist?region=MX",
    "search": "https://www.fastmoss.com/zh/e-commerce/search?region=MX",
}


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_STOP_REQUESTED = False


def check_stop_signal() -> bool:
    # 粘滞式停止标志：一旦收到停止信号，本进程内后续所有检查都返回 True
    global _STOP_REQUESTED
    if _STOP_REQUESTED:
        return True
    if os.path.exists(STOP_SIGNAL_PATH):
        try:
            os.remove(STOP_SIGNAL_PATH)
        except Exception:
            pass
        _STOP_REQUESTED = True
        return True
    return False


def clear_stop_signal() -> None:
    if os.path.exists(STOP_SIGNAL_PATH):
        try:
            os.remove(STOP_SIGNAL_PATH)
        except Exception:
            pass


def update_live_status(
    is_running: bool,
    progress_pct: int,
    message: str,
    items_collected: int = 0,
    board: str = "",
    page_num: int = 0,
    total_pages: int = 0,
    status: str = "RUNNING",
) -> None:
    payload = {
        "is_running": is_running,
        "status": status,
        "progress_pct": max(0, min(100, int(progress_pct))),
        "message": message,
        "items_collected": items_collected,
        "board": board,
        "page_num": page_num,
        "total_pages": total_pages,
        "updated_at": time.strftime("%H:%M:%S"),
    }
    try:
        with open(LIVE_STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass


def save_product_images(product_id: str, img_src: str, force_overwrite: bool = False) -> Tuple[str, str]:
    """
    双轨图片提纯与本地持久化：
    1. 缩略图 (96x96, 约 2~4KB): static/thumbs/<product_id>.jpg 用于看板、列表毫秒级极速渲染
    2. 高清大图 (540x540, 约 30~50KB): static/thumbs/<product_id>_large.jpg 用于常规专业商品网页(PDP)主图橱窗
    自动剔除店铺头像 (/tt_shop/)、默认占位符、logo与国旗
    返回: (thumb_url, large_url)
    """
    if not img_src or not product_id:
        return ("", "")
    clean_id = str(product_id).strip()
    m_pid = re.search(r"/(?:detail|productDetail)/(\d+)", clean_id)
    if not m_pid:
        m_pid = re.search(r"(\d+)", clean_id)
    if m_pid:
        clean_id = m_pid.group(1)

    if any(bad in img_src.lower() for bad in ("/tt_shop/", "default_avatar", "user_default", "flag", "country", "site_logo", "icon")):
        return ("", "")

    os.makedirs(THUMBS_DIR, exist_ok=True)
    out_thumb = os.path.join(THUMBS_DIR, f"{clean_id}.jpg")
    out_large = os.path.join(THUMBS_DIR, f"{clean_id}_large.jpg")
    rel_thumb = f"/thumbs/{clean_id}.jpg"
    rel_large = f"/thumbs/{clean_id}_large.jpg"

    has_thumb = os.path.exists(out_thumb) and os.path.getsize(out_thumb) > 200
    has_large = os.path.exists(out_large) and os.path.getsize(out_large) > 500

    if not force_overwrite and has_thumb and has_large:
        return (rel_thumb, rel_large)

    tmp_file = os.path.join(THUMBS_DIR, f"tmp_{clean_id}.img")
    try:
        if img_src.startswith("data:image/"):
            _, b64data = img_src.split(",", 1)
            with open(tmp_file, "wb") as f:
                f.write(base64.b64decode(b64data))
        elif img_src.startswith("http"):
            req = urllib.request.Request(
                img_src,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Referer": "https://www.fastmoss.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                with open(tmp_file, "wb") as f:
                    f.write(resp.read())
        else:
            return ("", "")

        # 跨平台图片压缩与缩略图生成 (优先使用 Pillow，其次 macOS sips，最后直接文件复制兜底)
        handled = False
        try:
            from PIL import Image
            with Image.open(tmp_file) as im:
                rgb_im = im.convert("RGB")
                # 1. 缩略图生成 (96x96, 55 质量)
                im_thumb = rgb_im.copy()
                im_thumb.thumbnail((96, 96))
                im_thumb.save(out_thumb, "JPEG", quality=55)
                # 2. 高清大图生成 (540x540, 80 质量)
                im_large = rgb_im.copy()
                im_large.thumbnail((540, 540))
                im_large.save(out_large, "JPEG", quality=80)
            handled = True
        except Exception:
            pass

        if not handled and sys.platform == "darwin" and os.path.exists("/usr/bin/sips"):
            # macOS 原生 sips 处理
            subprocess.run(
                ["/usr/bin/sips", "-Z", "96", "--setProperty", "format", "jpeg", "--setProperty", "formatOptions", "55", tmp_file, "--out", out_thumb],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            subprocess.run(
                ["/usr/bin/sips", "-Z", "540", "--setProperty", "format", "jpeg", "--setProperty", "formatOptions", "80", tmp_file, "--out", out_large],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            handled = True

        if not handled:
            try:
                shutil.copyfile(tmp_file, out_thumb)
                shutil.copyfile(tmp_file, out_large)
            except Exception:
                pass

        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass

        final_thumb = rel_thumb if (os.path.exists(out_thumb) and os.path.getsize(out_thumb) > 100) else (img_src if img_src.startswith("http") else "")
        final_large = rel_large if (os.path.exists(out_large) and os.path.getsize(out_large) > 100) else final_thumb
        return (final_thumb, final_large)
    except Exception:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        fallback = img_src if img_src.startswith("http") else ""
        return (fallback, fallback)


def save_tiny_thumbnail(product_id: str, img_src: str, force_overwrite: bool = False) -> str:
    """
    兼容保留微缩图提取接口，内部自动享受双轨高清生成
    """
    thumb, _ = save_product_images(product_id, img_src, force_overwrite=force_overwrite)
    return thumb


def parse_number(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = (
        str(val)
        .strip()
        .replace(",", "")
        .replace("MX$", "")
        .replace("$", "")
        .replace("MXN", "")
        .replace("¥", "")
        .replace("%", "")
    )
    mult = 1.0
    if s.lower().endswith("k") or s.endswith("千"):
        mult = 1000.0
        s = s[:-1]
    elif s.lower().endswith("w") or s.endswith("万"):
        mult = 10000.0
        s = s[:-1]
    elif s.lower().endswith("m") or s.endswith("亿"):
        mult = 1000000.0
        s = s[:-1]
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return float(m.group(0)) * mult if m else 0.0


def extract_products_from_dom(page: Any, board_label: str, page_index: int = 1) -> List[Dict[str, Any]]:
    """
    旗舰级全字段列表提取器：
    自适应新品榜、飙升榜、搜索页等所有不同表头结构，精准定位『商品』列提取真实主图（绝不误抓店铺头像）与内嵌三级分类
    """
    try:
        raw_table = page.evaluate(
            r"""() => {
                const headers = Array.from(document.querySelectorAll('.ant-table-thead th')).map(th => th.innerText.trim());
                const rows = [];
                document.querySelectorAll('.ant-table-tbody tr').forEach((tr, idx) => {
                    const tds = Array.from(tr.querySelectorAll('td'));
                    const cells = tds.map(td => td.innerText.trim());
                    const links = Array.from(tr.querySelectorAll('a')).map(a => ({ href: a.href, text: a.innerText.trim() }));
                    // 精准定位包含商品详情链接的那个 td 单元格（避免搜索页把 td[1] 店铺头像当成商品主图）
                    const prodTd = tds.find(td => {
                        const a = td.querySelector('a[href*="/detail/"], a[href*="/productDetail/"]');
                        return a && !a.href.includes('shop-marketing');
                    }) || tds[0] || tr;
                    const imgs = Array.from(prodTd.querySelectorAll('img'));
                    let bestImg = '';
                    for (const im of imgs) {
                        const src = im.currentSrc || im.src || im.getAttribute('data-src') || im.getAttribute('data-original') || '';
                        if (src && !src.includes('/tt_shop/') && !src.includes('flag') && !src.includes('country') && !src.includes('avatar') && !src.includes('default')) {
                            bestImg = src;
                            break;
                        }
                    }
                    if (cells.length >= 5 && cells.some(c => c.length > 5)) {
                        // 尝试提取『近7天销量趋势』单元格内的 SVG path 真实纵坐标高度
                        let svgWeights = [];
                        for (const td of tds) {
                            const pathEl = td.querySelector('svg path, svg polyline');
                            if (pathEl) {
                                const dAttr = pathEl.getAttribute('d') || pathEl.getAttribute('points') || '';
                                const coordPairs = Array.from(dAttr.matchAll(/[-+]?\d*\.?\d+\s*,\s*([-+]?\d*\.?\d+)/g)).map(m => parseFloat(m[1]));
                                if (coordPairs.length >= 5) {
                                    const maxY = Math.max(...coordPairs, 1);
                                    const minY = Math.min(...coordPairs, 0);
                                    const span = Math.max(1, maxY - minY);
                                    // SVG 坐标系 Y 越小代表柱/点越高
                                    const heights = coordPairs.slice(0, 7).map(y => Math.max(0.05, (maxY - y) / span + 0.12));
                                    if (heights.length === 7) svgWeights = heights;
                                    break;
                                }
                            }
                        }
                        rows.push({ rowIndex: idx + 1, cells, links, imgUrl: bestImg, svgWeights });
                    }
                });
                return { headers, rows, pageUrl: location.href };
            }"""
        )

        headers = raw_table.get("headers") or []
        rows = raw_table.get("rows") or []
        items: List[Dict[str, Any]] = []

        for r in rows:
            cells = r.get("cells") or []
            links = r.get("links") or []
            raw_img_url = r.get("imgUrl") or ""
            row_idx = int(r.get("rowIndex") or 1) + (page_index - 1) * 10

            prod_url = ""
            shop_url = ""
            pid = ""
            for lk_obj in links:
                lk = lk_obj.get("href") or ""
                if "shop-marketing" in lk:
                    shop_url = lk
                else:
                    m = re.search(r"/(?:detail|productDetail)/(\d+)", lk)
                    if m:
                        pid = m.group(1)
                        prod_url = lk
            if not pid:
                continue

            tiny_thumb_url, large_thumb_url = save_product_images(pid, raw_img_url)
            if not tiny_thumb_url:
                tiny_thumb_url = save_tiny_thumbnail(pid, raw_img_url)

            # 构建表头->单元格映射字典
            header_cell_map: Dict[str, str] = {}
            for idx, cell_text in enumerate(cells):
                h_name = headers[idx] if idx < len(headers) and headers[idx] else f"col_{idx}"
                header_cell_map[h_name] = cell_text

            rank_val = int(parse_number(header_cell_map.get("排名"))) if "排名" in header_cell_map else row_idx

            # 精准获取『商品』单元格（兼容搜索页在 cells[0]、榜单页在 cells[1]）
            prod_cell = header_cell_map.get("商品") or (cells[1] if len(cells) > 1 and "售价" in cells[1] else cells[0])
            parsed_prod = parse_fastmoss_product_cell_lines(prod_cell)

            title = parsed_prod["title"] or f"Producto MX {pid}"
            price_mxn = parsed_prod["price_mxn"] if parsed_prod["price_mxn"] > 1 else 259.0
            days_online = parsed_prod["days_online"]
            release_date = parsed_prod["release_date"] or (datetime.date.today() - datetime.timedelta(days=days_online)).strftime("%Y-%m-%d")
            rating_val = parsed_prod["rating"]
            commission_pct = parsed_prod["commission_pct"]

            shop_name = "Tienda MX"
            shop_total_sales = ""
            raw_category = parsed_prod["embedded_category"] or ""
            sales_3d = 0
            recent_sales = 0
            total_sales = 0
            gmv_3d_text = ""
            total_gmv_text = ""
            growth_rate = 120.0
            creators_count = 0

            for h_name, cell_text in header_cell_map.items():
                if "店铺" in h_name:
                    shop_lines = [x.strip() for x in cell_text.split("\n") if x.strip()]
                    if shop_lines:
                        shop_name = shop_lines[0]
                    for sl in shop_lines[1:]:
                        if "销量" in sl or "销" in sl:
                            shop_total_sales = sl.replace("店铺销量：", "").replace("店铺销量:", "").strip()
                elif "分类" in h_name or "类目" in h_name:
                    if cell_text and not cell_text.isdigit():
                        raw_category = cell_text.replace("\n", " > ")
                elif "佣金" in h_name:
                    c_val = parse_number(cell_text)
                    if 0 < c_val <= 80:
                        commission_pct = c_val
                elif "三日销量" in h_name:
                    sales_3d = int(parse_number(cell_text))
                    recent_sales = sales_3d
                elif "三日销售额" in h_name:
                    gmv_3d_text = cell_text
                elif any(k in h_name for k in ("近7天销量", "周销量", "7天销量", "日销量")) and "趋势" not in h_name:
                    recent_sales = int(parse_number(cell_text))
                elif any(k in h_name for k in ("近7天销售额", "周销售额", "销售额")) and "总" not in h_name and "三日" not in h_name:
                    gmv_3d_text = cell_text
                elif h_name == "总销量":
                    total_sales = int(parse_number(cell_text))
                elif h_name == "总销售额":
                    total_gmv_text = cell_text
                elif any(k in h_name for k in ("飙升", "增长", "环比", "涨幅")):
                    g_val = parse_number(cell_text)
                    if g_val > 0:
                        growth_rate = g_val
                elif "关联达人" in h_name or "达人" in h_name and "率" not in h_name:
                    creators_count = max(1, int(parse_number(cell_text)))

            main_cat, sub_cat = classify_category(raw_category, title)

            if sales_3d > 0 and recent_sales == sales_3d:
                sales_7d = int(sales_3d * 1.8) if total_sales > sales_3d else sales_3d
            else:
                sales_7d = recent_sales if recent_sales > 0 else max(int(total_sales * 0.35), 25)

            if total_sales < sales_7d:
                total_sales = sales_7d

            if days_online <= 10 and sales_7d >= 100:
                growth_rate = max(growth_rate, 185.0)
            elif sales_7d >= 300:
                growth_rate = max(growth_rate, 145.0)

            svg_weights = r.get("svgWeights") or []
            daily_series = build_realistic_7d_series(
                product_id=pid,
                sales_7d=sales_7d,
                total_sales=total_sales,
                days_online=days_online,
                sales_3d=sales_3d,
                growth_rate_7d=growth_rate,
                svg_weights=svg_weights if len(svg_weights) == 7 else None,
            )

            est_cost_rmb = round(max(5.5, (price_mxn / 2.80) * 0.18), 1)

            raw_snapshot = {
                "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "board": board_label,
                "page_url": raw_table.get("pageUrl", ""),
                "table_columns": header_cell_map,
                "links": links,
                "original_img_url": raw_img_url,
            }

            items.append(
                {
                    "product_id": pid,
                    "title": title,
                    "title_cn": f"[{sub_cat}] {title[:38]}",
                    "title_es": title,
                    "category": sub_cat,
                    "main_category": main_cat,
                    "sub_category": sub_cat,
                    "shop_name": shop_name,
                    "shop_type": "Mall品牌官方店" if "official" in shop_name.lower() or "oficial" in shop_name.lower() else "普通本土店",
                    "price_mxn": price_mxn,
                    "sales_3d": sales_3d if sales_3d > 0 else recent_sales,
                    "sales_7d": sales_7d,
                    "sales_28d": total_sales,
                    "total_sales": total_sales,
                    "gmv_7d_mxn": parse_number(gmv_3d_text) if gmv_3d_text else price_mxn * sales_7d,
                    "gmv_3d_text": gmv_3d_text or f"MX${(price_mxn * sales_7d):,.0f}",
                    "total_gmv_text": total_gmv_text or f"MX${(price_mxn * total_sales):,.0f}",
                    "growth_rate_7d": growth_rate,
                    "creators_7d": creators_count,
                    "videos_7d": creators_count * 2,
                    "top_creator_share_pct": 30.0,
                    "product_card_share_pct": 25.0,
                    "days_online": days_online,
                    "release_date": release_date,
                    "rank_num": rank_val,
                    "shop_url": shop_url,
                    "shop_total_sales": shop_total_sales or "热销本土店",
                    "commission_rate_pct": commission_pct,
                    "rating": rating_val,
                    "weight_g": 260.0,
                    "cost_1688_rmb": est_cost_rmb,
                    "image_url": tiny_thumb_url,
                    "image_large_url": large_thumb_url,
                    "fastmoss_url": prod_url or f"https://www.fastmoss.com/zh/e-commerce/detail/{pid}",
                    "daily_sales_series": daily_series,
                    "keywords_1688": [sub_cat, title[:20]],
                    "spanish_keywords": [title.split(" ")[0], sub_cat],
                    "raw_payload_json": raw_snapshot,
                    "source_board": board_label,
                }
            )
        return items
    except Exception as e:
        print("DOM parse error:", e)
        return []


def parse_fastmoss_detail_api_blobs(blobs: List[Dict[str, Any]], clean_pid: str) -> Dict[str, Any]:
    """
    智能解构 FastMoss 详情页拦截到的所有底包 JSON：
    1. 提取 30 天/多日真实日销序列 (daily_sales_series)
    2. 提取渠道出单分布 (channel_breakdown_json & product_card_share_pct)
    3. 提取带货达人详情 (top_creators_json)
    4. 提取真实爆款带货视频 (top_videos_json)
    5. 提取 SKU 规格颗粒度 (sku_specs_json)
    6. 提取实拍高清大图候选 (candidate_img)
    """
    res: Dict[str, Any] = {}
    best_series: List[Dict[str, Any]] = []
    best_creators: List[Dict[str, Any]] = []
    best_videos: List[Dict[str, Any]] = []
    best_skus: List[Dict[str, Any]] = []
    channel_info: Dict[str, float] = {}
    candidate_img: str = ""

    def scan_for_daily_series(obj: Any):
        nonlocal best_series
        if isinstance(obj, list) and len(obj) >= 5:
            matched_items = []
            for it in obj:
                if isinstance(it, dict):
                    d_val = str(it.get("date") or it.get("day") or it.get("time") or "")
                    if re.search(r"\d{2,4}[-/]\d{1,2}[-/]\d{1,2}", d_val) or re.search(r"^\d{2}[-/]\d{2}$", d_val):
                        s_val = parse_number(it.get("sales") or it.get("units") or it.get("count") or it.get("volume") or it.get("num") or it.get("order_count") or 0)
                        g_val = parse_number(it.get("gmv") or it.get("amount") or it.get("sales_amount") or 0.0)
                        matched_items.append({"date": d_val, "sales": int(s_val), "gmv": round(float(g_val), 2)})
            if len(matched_items) >= 5 and len(matched_items) > len(best_series):
                best_series = matched_items
        elif isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    scan_for_daily_series(v)

    def scan_for_creators(obj: Any):
        nonlocal best_creators
        if isinstance(obj, list) and len(obj) >= 1:
            matched_creators = []
            for it in obj:
                if isinstance(it, dict):
                    name = str(it.get("author_name") or it.get("nickname") or it.get("creator_name") or it.get("name") or "").strip()
                    if name and not any(k in name.lower() for k in ("table", "header", "null", "undefined")):
                        sales = int(parse_number(it.get("sales") or it.get("units") or it.get("order_num") or it.get("order_count") or 0))
                        fans = int(parse_number(it.get("fans") or it.get("follower_count") or it.get("followers") or 0))
                        gmv = parse_number(it.get("gmv") or it.get("sales_amount") or it.get("amount") or 0.0)
                        avatar = str(it.get("avatar") or it.get("head_img") or it.get("cover") or "")
                        uid = str(it.get("author_id") or it.get("uid") or it.get("unique_id") or "")
                        fans_txt = f"{fans // 1000}K" if fans >= 1000 else str(fans)
                        matched_creators.append({
                            "creator": name,
                            "uid": uid,
                            "avatar": avatar,
                            "sales": sales,
                            "fans": fans,
                            "gmv": gmv,
                            "metrics": [f"带货 {sales} 单", f"粉丝 {fans_txt}", f"GMV ${round(gmv)}"],
                        })
            if len(matched_creators) >= 1 and len(matched_creators) > len(best_creators):
                best_creators = matched_creators[:10]
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if any(x in k.lower() for x in ("author", "creator", "kol")):
                    scan_for_creators(v)
                elif isinstance(v, (dict, list)):
                    scan_for_creators(v)

    def scan_for_videos(obj: Any):
        nonlocal best_videos
        if isinstance(obj, list) and len(obj) >= 1:
            matched_videos = []
            for it in obj:
                if isinstance(it, dict):
                    title = str(it.get("video_title") or it.get("title") or it.get("desc") or "").strip()
                    vid = str(it.get("video_id") or it.get("item_id") or "")
                    plays = int(parse_number(it.get("play_count") or it.get("view_count") or it.get("plays") or 0))
                    sales = int(parse_number(it.get("sales") or it.get("order_count") or 0))
                    cover = str(it.get("cover") or it.get("cover_url") or it.get("poster") or "")
                    if title or vid or cover:
                        plays_txt = f"{plays // 1000}K" if plays >= 1000 else str(plays)
                        matched_videos.append({
                            "video": title or "带货爆款短视频",
                            "video_id": vid,
                            "cover": cover,
                            "plays": plays,
                            "sales": sales,
                            "metrics": [f"播放 {plays_txt}", f"出单 {sales} 单"],
                        })
            if len(matched_videos) >= 1 and len(matched_videos) > len(best_videos):
                best_videos = matched_videos[:8]
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if any(x in k.lower() for x in ("video", "short_video")):
                    scan_for_videos(v)
                elif isinstance(v, (dict, list)):
                    scan_for_videos(v)

    def scan_for_skus(obj: Any):
        nonlocal best_skus
        if isinstance(obj, list) and len(obj) >= 1:
            matched_skus = []
            for it in obj:
                if isinstance(it, dict):
                    sku_id = str(it.get("sku_id") or it.get("id") or it.get("spec_id") or "")
                    spec_name = str(it.get("sku_name") or it.get("spec_name") or it.get("spec_value") or it.get("title") or it.get("properties") or "").strip()
                    price = parse_number(it.get("price") or it.get("sale_price") or it.get("sku_price") or 0.0)
                    sales = int(parse_number(it.get("sales") or it.get("sale_num") or it.get("volume") or 0))
                    stock = int(parse_number(it.get("stock") or it.get("inventory") or 0))
                    img = str(it.get("image") or it.get("sku_img") or it.get("pic") or "")
                    if spec_name or sku_id:
                        matched_skus.append({
                            "sku_id": sku_id,
                            "spec_name": spec_name or f"规格 #{len(matched_skus)+1}",
                            "price_mxn": round(price, 2),
                            "sales": sales,
                            "stock": stock,
                            "image": img,
                        })
            if len(matched_skus) >= 1 and len(matched_skus) > len(best_skus):
                best_skus = matched_skus[:12]
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if any(x in k.lower() for x in ("sku", "spec", "variant")):
                    scan_for_skus(v)
                elif isinstance(v, (dict, list)):
                    scan_for_skus(v)

    def scan_for_channel_and_image(obj: Any):
        nonlocal channel_info, candidate_img
        if isinstance(obj, dict):
            v_rate = obj.get("video_rate") or obj.get("video_sales_rate") or obj.get("short_video_rate")
            l_rate = obj.get("live_rate") or obj.get("live_sales_rate")
            c_rate = obj.get("card_rate") or obj.get("product_card_rate") or obj.get("mall_rate")
            if v_rate is not None or l_rate is not None or c_rate is not None:
                vr = parse_number(v_rate or 0)
                lr = parse_number(l_rate or 0)
                cr = parse_number(c_rate or 0)
                total = vr + lr + cr
                if total > 0:
                    channel_info = {
                        "video_pct": round((vr / total) * 100 if total > 1.5 else vr, 1),
                        "live_pct": round((lr / total) * 100 if total > 1.5 else lr, 1),
                        "product_card_pct": round((cr / total) * 100 if total > 1.5 else cr, 1),
                        "other_pct": round(max(0.0, 100.0 - (vr + lr + cr)), 1),
                    }
            for k in ("cover", "image", "image_url", "pic_url", "main_img"):
                val = str(obj.get(k) or "")
                if val.startswith("http") and not any(bad in val.lower() for bad in ("/tt_shop/", "avatar", "logo", "flag")):
                    if not candidate_img or len(val) > len(candidate_img):
                        candidate_img = val
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    scan_for_channel_and_image(v)
        elif isinstance(obj, list):
            for it in obj:
                if isinstance(it, (dict, list)):
                    scan_for_channel_and_image(it)

    for b in blobs:
        data = b.get("data")
        if data:
            scan_for_daily_series(data)
            scan_for_creators(data)
            scan_for_videos(data)
            scan_for_skus(data)
            scan_for_channel_and_image(data)

    if best_series:
        res["daily_sales_series"] = best_series
    if best_creators:
        res["top_creators_json"] = best_creators
    if best_videos:
        res["top_videos_json"] = best_videos
    if best_skus:
        res["sku_specs_json"] = best_skus
    if channel_info:
        res["channel_breakdown_json"] = channel_info
        res["product_card_share_pct"] = channel_info.get("product_card_pct", 22.0)
    if candidate_img:
        res["candidate_img"] = candidate_img

    return res


def scrape_product_detail_page(page: Any, product_id: str, config: Dict[str, Any]) -> bool:
    """
    旗舰版/深潜模式二级穿透抓取：打开指定商品的 FastMoss 详情页，
    捕获该商品页面上的实拍高清主图(双轨大图/缩略图)、上架时间、真实 30 天日销、出单渠道占比、
    带货达人矩阵、爆款视频列表、SKU 规格颗粒度以及底层 API JSON 数据包，
    合并入库并标记 deep_scraped = 1（自动解锁 👑 旗舰全维实测评分）
    """
    # 清洗 product_id，若传入包含 URL 则自动解析出数字 ID
    m_pid = re.search(r"/(?:detail|productDetail)/(\d+)", str(product_id))
    if not m_pid:
        m_pid = re.search(r"(\d+)", str(product_id))
    clean_pid = m_pid.group(1) if m_pid else str(product_id).strip()

    existing = get_product_by_id(clean_pid) or get_product_by_id(str(product_id)) or {"product_id": clean_pid}
    detail_url = (
        str(product_id)
        if str(product_id).startswith("http")
        else (existing.get("fastmoss_url") or f"https://www.fastmoss.com/zh/e-commerce/detail/{clean_pid}")
    )
    detail_api_blobs: List[Dict[str, Any]] = []

    def on_detail_response(resp):
        try:
            ctype = resp.headers.get("content-type", "")
            if "json" in ctype and "fastmoss" in resp.url:
                if any(k in resp.url.lower() for k in ("product", "detail", "goods", "sale", "author", "creator", "video", "chart", "trend", "sku", "spec", "channel")):
                    detail_api_blobs.append({"url": resp.url, "data": resp.json()})
        except Exception:
            pass

    page.on("response", on_detail_response)
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(3800)
        for _ in range(3):
            page.mouse.wheel(0, 650)
            page.wait_for_timeout(650)

        dom_detail = page.evaluate(
            """() => {
                const bodyText = document.body ? document.body.innerText : '';
                // 1. 寻找页面面积最大且非头像的实拍商品大图
                let mainImg = '';
                let maxArea = 0;
                const imgs = Array.from(document.querySelectorAll('img'));
                for (const im of imgs) {
                    const src = im.currentSrc || im.src || im.getAttribute('data-src') || '';
                    const w = im.naturalWidth || im.clientWidth || 0;
                    const h = im.naturalHeight || im.clientHeight || 0;
                    const area = w * h;
                    if (src && src.startsWith('http') && !src.includes('/tt_shop/') && !src.includes('avatar') && !src.includes('logo') && !src.includes('flag')) {
                        if (area > maxArea && (w >= 100 || h >= 100)) {
                            maxArea = area;
                            mainImg = src;
                        }
                    }
                }
                // 2. 表格数据提取（达人、视频、规格）
                const tables = Array.from(document.querySelectorAll('table')).map(tb => {
                    const ths = Array.from(tb.querySelectorAll('th')).map(x => x.innerText.trim());
                    const trs = Array.from(tb.querySelectorAll('tbody tr')).slice(0, 10).map(tr =>
                        Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
                    );
                    return { ths, trs };
                });
                // 3. 提取渠道出单比例
                let channelDom = null;
                const mVideo = bodyText.match(/(?:短视频|视频带货)[^\\d]{0,8}(\\d{1,2}(?:\\.\\d+)?)\\s*%/);
                const mLive = bodyText.match(/(?:直播|直播带货)[^\\d]{0,8}(\\d{1,2}(?:\\.\\d+)?)\\s*%/);
                const mCard = bodyText.match(/(?:商品卡|自然流|商城)[^\\d]{0,8}(\\d{1,2}(?:\\.\\d+)?)\\s*%/);
                if (mVideo || mLive || mCard) {
                    channelDom = {
                        video_pct: mVideo ? parseFloat(mVideo[1]) : 65.0,
                        live_pct: mLive ? parseFloat(mLive[1]) : 20.0,
                        product_card_pct: mCard ? parseFloat(mCard[1]) : 15.0,
                        other_pct: 0.0,
                    };
                }
                // 4. SKU 芯片标签提取
                const skuChips = [];
                document.querySelectorAll('[class*="sku"], [class*="spec"], [class*="variant"]').forEach(el => {
                    const txt = el.innerText ? el.innerText.trim() : '';
                    if (txt && txt.length < 35 && !skuChips.includes(txt) && !txt.includes('\\n')) {
                        skuChips.push(txt);
                    }
                });
                return {
                    title: document.title,
                    mainImg,
                    tables,
                    channelDom,
                    skuChips: skuChips.slice(0, 15),
                    summarySnippet: bodyText.slice(0, 4000)
                };
            }"""
        )

        # 1. 深度解构 API Blobs 数据
        api_data = parse_fastmoss_detail_api_blobs(detail_api_blobs, clean_pid)

        # 2. 双轨图片提取与持久化 (优先使用实测高清大图)
        best_img = (
            api_data.get("candidate_img")
            or dom_detail.get("mainImg")
            or (existing.get("raw_payload_json") or {}).get("original_img_url")
            or existing.get("image_url")
            or ""
        )
        clean_large_disk = os.path.join(THUMBS_DIR, f"{clean_pid}_large.jpg")
        if os.path.exists(clean_large_disk) and os.path.getsize(clean_large_disk) > 500:
            existing["image_large_url"] = f"/thumbs/{clean_pid}_large.jpg"
        if best_img:
            t_url, l_url = save_product_images(clean_pid, best_img, force_overwrite=True)
            if t_url:
                existing["image_url"] = t_url
            if l_url:
                existing["image_large_url"] = l_url

        # 3. 真实日销趋势覆盖（真实 30 天 / 14 天真数据）
        if api_data.get("daily_sales_series"):
            s_series = api_data["daily_sales_series"]
            existing["daily_sales_series"] = s_series
            if len(s_series) >= 7:
                existing["sales_7d"] = sum(item["sales"] for item in s_series[-7:])
            if len(s_series) >= 3:
                existing["sales_3d"] = sum(item["sales"] for item in s_series[-3:])
            if len(s_series) >= 14:
                s_prev = sum(item["sales"] for item in s_series[-14:-7])
                s_curr = sum(item["sales"] for item in s_series[-7:])
                existing["growth_rate_7d"] = round(((s_curr - s_prev) / max(1, s_prev)) * 100, 1)

        # 4. 渠道出单结构覆盖
        if api_data.get("channel_breakdown_json"):
            existing["channel_breakdown_json"] = api_data["channel_breakdown_json"]
            existing["product_card_share_pct"] = api_data.get("product_card_share_pct", 22.0)
        elif dom_detail.get("channelDom"):
            existing["channel_breakdown_json"] = dom_detail["channelDom"]
            existing["product_card_share_pct"] = dom_detail["channelDom"].get("product_card_pct", 22.0)
        elif not existing.get("channel_breakdown_json") or existing["channel_breakdown_json"] == {}:
            existing["channel_breakdown_json"] = {
                "video_pct": 68.0,
                "live_pct": 18.0,
                "product_card_pct": 14.0,
                "other_pct": 0.0,
            }
            existing["product_card_share_pct"] = 14.0

        # 5. 达人与视频矩阵合并
        if api_data.get("top_creators_json"):
            existing["top_creators_json"] = api_data["top_creators_json"]
            existing["creators_7d"] = max(existing.get("creators_7d") or 0, len(api_data["top_creators_json"]))
        else:
            top_creators = []
            for tb in dom_detail.get("tables", []):
                ths_str = " ".join(tb.get("ths", []))
                if "达人" in ths_str:
                    for r in tb.get("trs", [])[:8]:
                        if r:
                            top_creators.append({"creator": r[0][:40], "metrics": r[1:4]})
            if top_creators:
                existing["top_creators_json"] = top_creators
                existing["creators_7d"] = max(existing.get("creators_7d") or 0, len(top_creators))

        if api_data.get("top_videos_json"):
            existing["top_videos_json"] = api_data["top_videos_json"]
            existing["videos_7d"] = max(existing.get("videos_7d") or 0, len(api_data["top_videos_json"]))
        else:
            top_videos = []
            for tb in dom_detail.get("tables", []):
                ths_str = " ".join(tb.get("ths", []))
                if "视频" in ths_str or "播放" in ths_str:
                    for r in tb.get("trs", [])[:8]:
                        if r:
                            top_videos.append({"video": r[0][:50], "metrics": r[1:4]})
            if top_videos:
                existing["top_videos_json"] = top_videos
                existing["videos_7d"] = max(existing.get("videos_7d") or 0, len(top_videos))

        # 6. SKU 规格颗粒度数据合并
        if api_data.get("sku_specs_json"):
            existing["sku_specs_json"] = api_data["sku_specs_json"]
        elif dom_detail.get("skuChips"):
            chips = dom_detail["skuChips"]
            base_p = float(existing.get("price_mxn") or 299)
            existing["sku_specs_json"] = [
                {
                    "sku_id": f"{clean_pid}_{i+1}",
                    "spec_name": chip,
                    "price_mxn": round(base_p * (1.0 + (i * 0.05)), 1),
                    "sales": max(5, int((int(existing.get("sales_7d") or 80) * 0.4) / (i + 1))),
                    "stock": 100,
                    "image": existing.get("image_url") or "",
                }
                for i, chip in enumerate(chips[:8])
            ]

        # 7. 从详情页正文提取上架日期与其余补充指标
        snippet = dom_detail.get("summarySnippet") or ""
        m_rel = re.search(r"(202[3-6]-\d{2}-\d{2})", snippet)
        if m_rel:
            existing["release_date"] = m_rel.group(1)

        m_cre = re.search(r"(?:关联达人|带货达人|达人数)[^\\d]{0,8}(\\d{1,5})", snippet)
        if m_cre and not existing.get("creators_7d"):
            existing["creators_7d"] = max(1, int(m_cre.group(1)))

        m_vid = re.search(r"(?:关联视频|带货视频|视频数)[^\\d]{0,8}(\\d{1,5})", snippet)
        if m_vid and not existing.get("videos_7d"):
            existing["videos_7d"] = max(1, int(m_vid.group(1)))

        raw_payload = existing.get("raw_payload_json") or {}
        if not isinstance(raw_payload, dict):
            raw_payload = {}
        raw_payload["detail_page_scraped_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        raw_payload["detail_dom_tables"] = dom_detail.get("tables", [])
        raw_payload["detail_api_responses"] = detail_api_blobs[:12]

        # 严格判定：只有当成功捕获到底层 API 数据包，或实际解析出真实 SKU / 真实日销 / 真实达人时，才标记为已深潜
        has_real_deep_data = bool(
            len(detail_api_blobs) > 0
            or api_data.get("daily_sales_series")
            or api_data.get("sku_specs_json")
            or api_data.get("top_creators_json")
            or (dom_detail.get("skuChips") and len(dom_detail["skuChips"]) > 0)
        )

        existing["raw_payload_json"] = raw_payload
        existing["deep_scraped"] = 1 if has_real_deep_data else 0
        upsert_product(existing, config)
        return has_real_deep_data
    except Exception:
        return False
    finally:
        try:
            page.remove_listener("response", on_detail_response)
        except Exception:
            pass


def extract_products_from_json_payload(payload: Any, board_label: str) -> List[Dict[str, Any]]:
    extracted = []
    if isinstance(payload, dict):
        if ("product_id" in payload or "productId" in payload) and (
            "title" in payload or "product_name" in payload or "price" in payload
        ):
            pid = str(payload.get("product_id") or payload.get("productId") or "")
            title = str(payload.get("title") or payload.get("product_name") or "")
            price = parse_number(payload.get("price") or payload.get("sale_price") or 259.0)
            s7 = int(parse_number(payload.get("sales_7d") or payload.get("day3_units") or payload.get("day7_units") or 80))
            tot = int(parse_number(payload.get("total_sales") or payload.get("total_units") or s7))
            raw_img = str(payload.get("image_url") or payload.get("cover") or payload.get("pic_url") or "")
            thumb = save_tiny_thumbnail(pid, raw_img) if pid and raw_img else ""
            extracted.append(
                {
                    "product_id": pid,
                    "title": title,
                    "title_cn": title,
                    "title_es": title,
                    "category": str(payload.get("category_name") or "墨西哥热销"),
                    "shop_name": str(payload.get("shop_name") or "Tienda MX"),
                    "price_mxn": price if price > 1 else 259.0,
                    "sales_7d": s7,
                    "sales_28d": tot,
                    "total_sales": tot,
                    "growth_rate_7d": parse_number(payload.get("growth_rate") or 125.0),
                    "image_url": thumb,
                    "raw_payload_json": payload,
                    "source_board": board_label,
                }
            )
        else:
            for v in payload.values():
                if isinstance(v, (dict, list)):
                    extracted.extend(extract_products_from_json_payload(v, board_label))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                extracted.extend(extract_products_from_json_payload(item, board_label))
    return extracted


def sync_flagship_plugin_state(profile_dir: str = PROFILE_DIR, copy_cookies: bool = True) -> bool:
    """
    将用户在主 Chrome (Default) 中已登录的 FastMoss 旗舰版插件状态
    (cardNumber / token / 绑定的原始 deviceFp / 旗舰版 Cookies) 无损同步到巡航专用的 profile 中，
    确保加载同一插件时不发生 deviceFp 变化，直接继承旗舰版 VIP 会员权限。
    """
    default_dir = os.path.join(profile_dir, "Default")
    os.makedirs(default_dir, exist_ok=True)
    synced = False

    # 1. 同步插件 Local Extension Settings (LevelDB 存储的 cardNumber, token, deviceFp, proxy)
    src_ext_settings = os.path.join(USER_CHROME_DEFAULT_DIR, "Local Extension Settings", MOSS_EXT_ID)
    dst_ext_settings = os.path.join(default_dir, "Local Extension Settings", MOSS_EXT_ID)
    def _latest_mtime(d: str) -> float:
        try:
            return max(
                (os.path.getmtime(os.path.join(d, f)) for f in os.listdir(d) if f != "LOCK"),
                default=0.0,
            )
        except Exception:
            return 0.0

    # 仅当主 Chrome 中的插件凭证比巡航专用 profile 更新时才覆盖（避免用旧 token 覆盖巡航窗口中新激活的会话）
    need_copy = os.path.exists(src_ext_settings) and (
        not os.path.exists(dst_ext_settings) or _latest_mtime(src_ext_settings) > _latest_mtime(dst_ext_settings)
    )
    if need_copy:
        try:
            # 整目录替换，避免新旧 LevelDB 日志文件混杂导致数据损坏
            if os.path.exists(dst_ext_settings):
                shutil.rmtree(dst_ext_settings, ignore_errors=True)
            os.makedirs(dst_ext_settings, exist_ok=True)
            for fname in os.listdir(src_ext_settings):
                if fname == "LOCK":
                    continue
                s_file = os.path.join(src_ext_settings, fname)
                d_file = os.path.join(dst_ext_settings, fname)
                if os.path.isfile(s_file):
                    shutil.copy2(s_file, d_file)
            lock_f = os.path.join(dst_ext_settings, "LOCK")
            if os.path.exists(lock_f):
                try:
                    os.remove(lock_f)
                except Exception:
                    pass
            synced = True
        except Exception:
            pass

    # 2. 同步主 Chrome 已注入的旗舰版 Cookies 数据库
    src_cookies = os.path.join(USER_CHROME_DEFAULT_DIR, "Cookies")
    dst_cookies = os.path.join(default_dir, "Cookies")
    if copy_cookies and os.path.exists(src_cookies):
        try:
            shutil.copy2(src_cookies, dst_cookies)
        except Exception:
            pass

    return synced


def clean_profile_conflicts(profile_dir: str = PROFILE_DIR, sync_plugin: bool = True, copy_cookies: bool = True) -> None:
    os.makedirs(profile_dir, exist_ok=True)
    for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lock_path = os.path.join(profile_dir, lock_name)
        if os.path.lexists(lock_path):
            try:
                os.remove(lock_path)
            except Exception:
                pass

    default_dir = os.path.join(profile_dir, "Default")
    if os.path.exists(default_dir):
        bad_prefixes = (
            "Web Data",
            "History",
            "Top Sites",
            "Shortcuts",
            "Affiliation Database",
            "Login Data",
            "Account Web Data",
            "Favicons",
            "Network Action Predictor",
            "DIPS",
        )
        for fname in os.listdir(default_dir):
            if any(fname.startswith(p) for p in bad_prefixes):
                try:
                    os.remove(os.path.join(default_dir, fname))
                except Exception:
                    pass

    pref_file = os.path.join(default_dir, "Preferences")
    if os.path.exists(pref_file):
        try:
            with open(pref_file, "r", encoding="utf-8") as f:
                prefs = json.load(f)
            if "profile" in prefs and isinstance(prefs["profile"], dict):
                prefs["profile"]["exit_type"] = "Normal"
                prefs["profile"]["exited_cleanly"] = True
            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(prefs, f)
        except Exception:
            pass

    # 同步主浏览器中已激活的 FastMoss 旗舰版插件凭证与 Cookies
    if sync_plugin:
        sync_flagship_plugin_state(profile_dir, copy_cookies=copy_cookies)


def get_moss_extension_path() -> str:
    if os.path.exists(MOSS_EXT_PRIMARY_PATH) and os.path.exists(os.path.join(MOSS_EXT_PRIMARY_PATH, "manifest.json")):
        return MOSS_EXT_PRIMARY_PATH
    if os.path.exists(MOSS_EXT_FALLBACK_PATH) and os.path.exists(os.path.join(MOSS_EXT_FALLBACK_PATH, "manifest.json")):
        return MOSS_EXT_FALLBACK_PATH
    return ""


def launch_real_chrome_context(p: Any, headless: bool = False):
    """
    重要说明：Google Chrome 正式版自 137 起已移除 --load-extension 命令行参数（本机为 Chrome 156），
    因此用正式版 Chrome 启动时插件会被静默忽略。
    有旗舰版插件时，改用 Playwright 自带的 Chromium 内核（仍支持 --load-extension）+ 独立的旗舰版专用 profile，
    解包插件的 Extension ID 由插件目录路径决定，因此 ID 与主 Chrome 中完全一致 (bhmemdccgceiofhgpagfieicgaabdgpl)。
    """
    ext_path = get_moss_extension_path()
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--noerrdialogs",
        "--disable-infobars",
        "--window-size=1280,820",
    ]

    # 关键：必须将 --disable-extensions 从 Playwright 默认参数中移除，否则旗舰版插件不会加载
    ignored_defaults = [
        "--enable-automation",
        "--no-sandbox",
        "--disable-extensions",
        "--disable-component-extensions-with-background-pages",
    ]

    if ext_path:
        # Chromium 与正式版 Chrome 的 Cookie 加密钥匙串不同，不拷贝 Cookies，由插件后台自行注入最新旗舰版 Cookie
        clean_profile_conflicts(FLAGSHIP_PROFILE_DIR, sync_plugin=True, copy_cookies=False)
        launch_args.extend(
            [
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
            ]
        )
        return p.chromium.launch_persistent_context(
            user_data_dir=FLAGSHIP_PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            args=launch_args,
            ignore_default_args=ignored_defaults,
        )

    clean_profile_conflicts(PROFILE_DIR, sync_plugin=False)
    if os.path.exists(CHROME_MAC_PATH):
        return p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            executable_path=CHROME_MAC_PATH,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            args=launch_args,
            ignore_default_args=ignored_defaults,
        )
    return p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=headless,
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        args=launch_args,
        ignore_default_args=ignored_defaults,
    )


def ensure_flagship_plugin_session(context: Any, page: Any) -> Tuple[Any, Dict[str, Any]]:
    """
    通过旗舰版插件后台 Service Worker (background.js) 直接校验并激活专属代理与旗舰版 Cookie：
    1. 绝不打开 warning.html 或 popup.html（既不触发重算 deviceFp，也不会残留 warning.html 标签页造成误判）；
    2. 优先调用 checkLoginStatus() 校验现有 token + 检查浏览器是否已有 .fastmoss.com 登录 Cookie：
       - 若 token 仍有效且 Cookie 已在库，直接复用现有会话与代理（不重新请求 /index/login/index，绝不把主 Chrome 踢下线）；
       - 仅当 Cookie 缺失或 token 失效时，才调用 fetchProxyAndCookie(cardNumber) 拉取最新 Cookie。
    """
    info: Dict[str, Any] = {"active": False, "cardNumber": "", "msg": "标准会话"}
    ext_path = get_moss_extension_path()
    if not ext_path:
        return page, info

    try:
        sw = next((w for w in context.service_workers if MOSS_EXT_ID in (w.url or "")), None)
        if not sw:
            try:
                sw = context.wait_for_event("serviceworker", timeout=10000)
            except Exception:
                sw = next((w for w in context.service_workers if MOSS_EXT_ID in (w.url or "")), None)

        info["ext_loaded"] = bool(sw)
        if not sw:
            info["msg"] = "⚠️ 旗舰版插件未能加载"
            return page, info

        page.wait_for_timeout(1000)
        try:
            existing_fm_cookies = context.cookies("https://www.fastmoss.com")
        except Exception:
            existing_fm_cookies = []
        has_fm_cookies = len(existing_fm_cookies) >= 3

        res = sw.evaluate(
            r"""async (hasFmCookies) => {
                const data = await chrome.storage.local.get(['cardNumber', 'token', 'deviceFp', 'proxy']);
                if (!data || !data.cardNumber) {
                    return { ok: false, reason: 'no_card_number', data: data || {} };
                }
                state.cardNumber = data.cardNumber;
                state.token = data.token || '';
                state.kickedOut = false;

                // 优先用只读接口 /index/login/info 检查当前 token 是否有效，避免无谓刷新 token
                if (data.token && data.proxy && hasFmCookies) {
                    try {
                        const st = await checkLoginStatus();
                        if (st === 'valid') {
                            const parts = String(data.proxy).split(':');
                            if (parts.length >= 4) {
                                state.currentProxy = {
                                    host: parts[0],
                                    port: parseInt(parts[1], 10),
                                    username: parts[2],
                                    password: parts[3]
                                };
                                await setProxy(state.currentProxy);
                            }
                            await removeBlockRule();
                            await removeScrapeRules();
                            state.lastVerifiedTime = Date.now();
                            return {
                                ok: true,
                                reused: true,
                                cardNumber: data.cardNumber,
                                hasToken: true
                            };
                        }
                    } catch (e) {}
                }

                // 仅当首次启动无 Cookie 或旧 token 已失效时，调用 fetchProxyAndCookie 注入最新旗舰版 Cookie
                const resp = await fetchProxyAndCookie(data.cardNumber);
                return {
                    ok: Boolean(resp && resp.success),
                    reused: false,
                    cardNumber: data.cardNumber,
                    hasToken: Boolean(state.token),
                    resp: resp || {}
                };
            }""",
            has_fm_cookies,
        )

        if isinstance(res, dict) and res.get("cardNumber"):
            info["cardNumber"] = str(res.get("cardNumber"))
            info["active"] = bool(res.get("ok") or res.get("hasToken"))
            mode_note = "无损复用" if res.get("reused") else "全新注入"
            info["msg"] = f"👑 旗舰版插件已激活 ({info['cardNumber'][:4]}***·{mode_note})"

        page.wait_for_timeout(1800)
        fm_pages = [p for p in context.pages if "fastmoss.com" in (p.url or "")]
        active_page = fm_pages[-1] if fm_pages else page
        active_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        for p_item in list(context.pages):
            if p_item != active_page and ("chrome-extension://" in (p_item.url or "") or p_item.url == "about:blank"):
                try:
                    p_item.close()
                except Exception:
                    pass
        return active_page, info
    except Exception as e:
        info["msg"] = f"插件同步就绪 ({e})"

    return page, info


# ==================== 断点续抓 / 安全守卫 / 类目筛选 辅助函数 ====================

CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "cruise_checkpoint.json")

BOARD_LABEL_MAP = {
    "new": "墨西哥新品榜",
    "soaring": "墨西哥销量飙升榜",
    "hot": "墨西哥热销商品榜",
    "search": "墨西哥全量商品库",
}


def is_main_chrome_running() -> bool:
    """检测用户日常使用的正式版 Google Chrome 是否在运行（跨平台兼容，避免多开踢号）。"""
    try:
        if sys.platform == "win32":
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"], capture_output=True, text=True, check=False)
            return "chrome.exe" in (r.stdout or "").lower()
        else:
            r = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True, text=True, check=False)
            return bool((r.stdout or "").strip())
    except Exception:
        return False


def load_checkpoint() -> Dict[str, Any]:
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_checkpoint(data: Dict[str, Any]) -> None:
    data = dict(data)
    data["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def clear_checkpoint() -> None:
    try:
        if os.path.exists(CHECKPOINT_PATH):
            os.remove(CHECKPOINT_PATH)
    except Exception:
        pass


DEEP_CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "deep_checkpoint.json")


def load_deep_checkpoint() -> Dict[str, Any]:
    if os.path.exists(DEEP_CHECKPOINT_PATH):
        try:
            with open(DEEP_CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_deep_checkpoint(data: Dict[str, Any]) -> None:
    data = dict(data)
    data["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(DEEP_CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def clear_deep_checkpoint() -> None:
    try:
        if os.path.exists(DEEP_CHECKPOINT_PATH):
            os.remove(DEEP_CHECKPOINT_PATH)
    except Exception:
        pass


def read_plugin_warning(context: Any) -> Optional[Dict[str, str]]:
    """若插件弹出了 warning.html，读取其标题与原因文案，返回 {kind, title, text}。"""
    for p_tab in list(context.pages):
        url = p_tab.url or ""
        if "warning.html" not in url:
            continue
        title, text = "", ""
        try:
            p_tab.wait_for_timeout(800)
            title = p_tab.evaluate("() => (document.querySelector('h1') || {}).innerText || ''") or ""
            text = p_tab.evaluate("() => (document.querySelector('p') || {}).innerText || ''") or ""
        except Exception:
            pass
        blob = title + text
        if "频繁" in blob or "批量" in blob or "频率" in blob:
            kind = "rate"
        elif "网络" in blob:
            kind = "ip"
        else:
            kind = "kicked"
        return {"kind": kind, "title": title.strip() or "插件安全提醒", "text": text.strip()}
    return None


def apply_category_filter(page: Any, category: str) -> bool:
    """在 FastMoss 榜单页的「商品分类」筛选区点击指定一级类目（按可见文字匹配，找不到则返回 False 继续抓全部类目）。"""
    if not category:
        return True
    try:
        loc = page.get_by_text(category, exact=True)
        cnt = loc.count()
        for i in range(min(cnt, 6)):
            el = loc.nth(i)
            if el.is_visible():
                el.scroll_into_view_if_needed()
                page.wait_for_timeout(random.randint(600, 1100))
                el.click()
                page.wait_for_timeout(random.randint(3800, 5600))
                return True
    except Exception:
        pass
    return False


def build_board_page_url(base_url: str, page_num: int) -> str:
    """构建带目标起始页的 URL，首次 page.goto 即直达目标页，避免从第 1 页多余加载和跳转开销。"""
    if page_num <= 1:
        return base_url
    delimiter = "&" if "?" in base_url else "?"
    return f"{base_url}{delimiter}page={page_num}&pageNum={page_num}"


def get_active_list_page(page: Any) -> int:
    """仅从 DOM 中高亮选中的分页项（如 li.ant-pagination-item-active）读取当前真实激活的页码，绝不依赖 URL query。"""
    try:
        el = page.query_selector(".ant-pagination-item-active, li.ant-pagination-item-active, [aria-current='page']")
        if el:
            t = (el.get_attribute("title") or el.inner_text() or "").strip()
            m = re.search(r"\d+", t)
            if m:
                return int(m.group(0))
    except Exception:
        pass
    return 1


def goto_list_page(page: Any, target_pg: int) -> int:
    """
    断点续抓 / 指定起始页直达：
    针对 FastMoss 的 Ant Design 分页器，必须平滑滚动到底部，在「跳至 [ ] 页」输入框中输入目标页码并回车，
    等待列表异步刷新、高亮页码变为目标页后方视为跳转成功。若跳页输入框未就绪，则使用「...」向后跳5页拟人化快进。
    """
    if target_pg <= 1:
        return 1

    # 1. 先将视口平滑滚动到底部，确保分页器（包含跳至输入框）完全渲染在 DOM 中
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(random.randint(800, 1200))
    except Exception:
        pass

    # 2. 检查当前是否已经在目标页
    cur = get_active_list_page(page)
    if cur == target_pg:
        return cur

    # 3. 核心：在 FastMoss 分页器的「跳至 [ ] 页」输入框中填写数字并回车
    try:
        jumper_handle = page.evaluate_handle(r"""() => {
            const allInputs = Array.from(document.querySelectorAll('input'));
            const found = allInputs.find(inp => {
                const parentText = (inp.parentElement?.innerText || '') + (inp.closest('.ant-pagination')?.innerText || '');
                return parentText.includes('跳至') || parentText.includes('跳 到') || parentText.includes('跳');
            });
            if (found) return found;
            return document.querySelector('.ant-pagination-options-quick-jumper input, .ant-pagination-options input, .ant-pagination input');
        }""")
        jumper = jumper_handle.as_element()
        if jumper:
            jumper.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            jumper.click()
            page.wait_for_timeout(200)
            # 全选并清空旧值
            jumper.press("Meta+A")
            jumper.press("Control+A")
            jumper.press("Backspace")
            page.wait_for_timeout(200)
            # 拟人化逐字敲入数字
            jumper.type(str(target_pg), delay=100)
            page.wait_for_timeout(300)
            # 回车触发跳转
            jumper.press("Enter")

            # 辅助派发 React/Vue 所需的 input/change 与 Enter 键盘事件
            page.evaluate(
                r"""(target) => {
                    const allInputs = Array.from(document.querySelectorAll('input'));
                    const inp = allInputs.find(i => {
                        const parentText = (i.parentElement?.innerText || '') + (i.closest('.ant-pagination')?.innerText || '');
                        return parentText.includes('跳至') || parentText.includes('跳 到') || parentText.includes('跳');
                    }) || document.querySelector('.ant-pagination-options-quick-jumper input, .ant-pagination-options input, .ant-pagination input');
                    if (inp) {
                        inp.focus();
                        inp.value = target;
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                        const keDown = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true });
                        inp.dispatchEvent(keDown);
                        const keUp = new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true });
                        inp.dispatchEvent(keUp);
                    }
                }""",
                str(target_pg),
            )

            # 轮询等待 FastMoss 加载新列表，直到当前激活页高亮变为目标页
            for _ in range(18):
                page.wait_for_timeout(600)
                cur = get_active_list_page(page)
                if cur == target_pg:
                    return cur
    except Exception:
        pass

    # 4. 退化方案：逐步点击（目标页 ≤ 500 时最多约 150 次）
    for _ in range(150):
        if check_stop_signal():
            break
        cur = get_active_list_page(page)
        if cur >= target_pg:
            return cur
        btn = page.query_selector(f"li.ant-pagination-item-{target_pg}, li[title='{target_pg}']")
        if not btn and target_pg - cur > 5:
            btn = page.query_selector("li.ant-pagination-jump-next, .ant-pagination-jump-next")
        if not btn:
            btn = page.query_selector("li.ant-pagination-next:not(.ant-pagination-disabled), .ant-pagination-next:not(.ant-pagination-disabled)")
        if not btn:
            return cur
        try:
            btn.scroll_into_view_if_needed()
            page.wait_for_timeout(random.randint(600, 1000))
            btn.click()
            page.wait_for_timeout(random.randint(3200, 4800))
        except Exception:
            return get_active_list_page(page)
    return get_active_list_page(page)


def run_playwright_collector(
    mode: str,
    boards: List[str],
    pages: int,
    target: str,
    deep: bool,
    task_id: Optional[int] = None,
    categories: Optional[List[str]] = None,
    resume: bool = False,
    search_pages: int = 500,
    search_start: int = 1,
    start_page: int = 1,
) -> None:
    clear_stop_signal()
    config = load_config()
    init_db(config)

    from playwright.sync_api import sync_playwright

    # 连续抓取页数上限提升至 500 页，并支持从用户指定的起始页开始采集
    is_cruise = mode in ("cruise", "companion")
    max_pages_per_board = min(500, max(1, pages if pages >= 5 else (25 if is_cruise else pages)))
    start_page_val = min(500, max(1, int(start_page or 1)))

    # 抓取计划 = 榜单 × 一级类目 组合（未选类目 = 全部类目）
    # 全量商品库 (search) 与普通榜单均支持自定义起始页与最高 500 页上限
    search_pages = min(500, max(1, int(search_pages or max_pages_per_board)))
    search_start = min(search_pages, max(1, int(search_start or start_page_val)))
    cat_list = [c for c in (categories or []) if c] or [""]
    plan: List[Dict[str, Any]] = [
        {
            "board": b,
            "category": c,
            "max_pages": max(search_start, search_pages) if b == "search" else max(start_page_val, max_pages_per_board),
            "start_page": search_start if b == "search" else min(start_page_val, max_pages_per_board),
        }
        for b in boards
        for c in cat_list
    ]
    start_task_idx, resume_start_page = 0, None
    collected_count = 0

    # 断点续抓：恢复上次中断的计划、榜单位置与页码
    if resume and mode in ("cruise", "companion", "batch"):
        ck = load_checkpoint()
        if ck.get("plan"):
            plan = ck["plan"]
            max_pages_per_board = int(ck.get("max_pages", max_pages_per_board))
            start_task_idx = int(ck.get("task_idx", 0))
            resume_start_page = int(ck.get("next_page", 1))
            collected_count = int(ck.get("collected", 0))
            mode = ck.get("mode", mode)
            is_cruise = mode in ("cruise", "companion")
            boards = sorted({t["board"] for t in plan})

    def _task_pages(t: Dict[str, Any]) -> int:
        mx = int(t.get("max_pages") or max_pages_per_board)
        st = max(1, int(t.get("start_page") or 1))
        return max(1, mx - st + 1)

    total_steps = max(1, sum(_task_pages(t) for t in plan))
    current_step_num = sum(_task_pages(t) for t in plan[:start_task_idx]) + max(
        0, (resume_start_page or start_page_val) - max(1, int(plan[start_task_idx].get("start_page") or 1)) if start_task_idx < len(plan) else 0
    )
    consecutive_pages_scraped = 0
    high_score_pids_for_deep: List[str] = []

    update_live_status(
        True,
        6,
        f"🚀 正在{'恢复上次进度' if resume and start_task_idx + start_page > 1 else '启动'}{'【无人值守防风控自动巡航】' if is_cruise else '【一键快速采集】'}引擎 (正在挂载 FastMoss 旗舰版插件通道)...",
        collected_count,
        ",".join(boards),
        current_step_num,
        total_steps,
    )

    try:
        with sync_playwright() as p:
            context = launch_real_chrome_context(p, headless=False)
            page = context.pages[0] if context.pages else context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

            # 自动挂载并激活用户在 Chrome 中已登录的 FastMoss 旗舰版插件会话
            page, plugin_info = ensure_flagship_plugin_session(context, page)
            vip_tag = plugin_info.get("msg", "👑 旗舰版插件通道")

            if mode == "login":
                update_live_status(True, 30, f"🔑 已打开 FastMoss 窗口 ({vip_tag})，请确认右上角旗舰版账号已登录后关闭该窗口即可", 0, "登录验证", 1, 1)
                log_scrape_task(mode, "FastMoss登录窗口", "WAITING_USER_LOGIN", 0, f"等待确认登录状态 ({vip_tag})，关闭浏览器窗口即完成", task_id=task_id)
                if "fastmoss.com" not in (page.url or ""):
                    page.goto("https://www.fastmoss.com/zh/", wait_until="domcontentloaded", timeout=45000)
                while len(context.pages) > 0:
                    if context.pages[0].is_closed() or check_stop_signal():
                        break
                    time.sleep(1.0)
                update_live_status(False, 100, f"✅ 登录态验证并保存完成！({vip_tag})", 0, "登录验证", 1, 1, status="SUCCESS")
                log_scrape_task(mode, "FastMoss登录窗口", "SUCCESS", 0, f"✅ 登录会话已永久保存 ({vip_tag})", task_id=task_id)
                return

            elif mode in ("item", "deep_batch"):
                d_ck = load_deep_checkpoint() if resume else {}
                raw_parts = [x.strip() for x in target.split(",") if x.strip()]
                pid_list = []
                for rp in raw_parts:
                    m = re.search(r"/(?:detail|productDetail)/(\d+)", rp)
                    if not m:
                        m = re.search(r"(\d+)", rp)
                    pid_list.append(m.group(1) if m else rp)

                if resume and d_ck.get("pending_pids"):
                    pid_list = d_ck["pending_pids"]
                    done_d = len(d_ck.get("done_pids", []))
                    total_d = int(d_ck.get("total", len(pid_list) + done_d))
                else:
                    total_d = max(1, len(pid_list))
                    done_d = 0

                completed_pids = list(d_ck.get("done_pids", [])) if resume else []

                for idx_p, pid in enumerate(pid_list, 1):
                    current_overall_idx = done_d + 1
                    if check_stop_signal():
                        save_deep_checkpoint({
                            "total": total_d,
                            "done_pids": completed_pids,
                            "pending_pids": pid_list[idx_p - 1:],
                            "current_pid": pid,
                            "is_paused": True,
                        })
                        stop_msg = f"⏸️ 已安全暂停批量深潜任务（已完成 {done_d}/{total_d} 款），断点已保存，可随时无缝恢复续潜！"
                        update_live_status(False, int((done_d / total_d) * 100), stop_msg, done_d, "详情页静默深潜", done_d, total_d, status="PAUSED")
                        log_scrape_task(mode, f"深潜暂停 ({done_d}/{total_d})", "PAUSED", done_d, stop_msg, task_id=task_id)
                        return

                    # 实时检测 FastMoss 插件风控警报（异地掉线/频繁限制，防止账号离线后盲跑空转）
                    w = read_plugin_warning(context)
                    if w:
                        save_deep_checkpoint({
                            "total": total_d,
                            "done_pids": completed_pids,
                            "pending_pids": pid_list[idx_p - 1:],
                            "current_pid": pid,
                            "is_paused": True,
                        })
                        tip = "原因：同一张旗舰卡在另一处同时在线。" if w["kind"] == "kicked" else ("原因：插件判定请求频率过高。" if w["kind"] == "rate" else "原因：网络验证失败。")
                        warn_msg = f"🛡️ 插件提示【{w['title']}】，深潜任务已自动停机并保存断点（已有效完成 {done_d}/{total_d} 款）。{tip}"
                        update_live_status(False, pct_d, warn_msg, done_d, "详情页静默深潜", current_overall_idx, total_d, status="ERROR")
                        log_scrape_task(mode, f"深潜风控中断 ({done_d}/{total_d})", "ERROR", done_d, warn_msg, task_id=task_id)
                        return

                    pct_d = int(5 + (current_overall_idx / total_d) * 90)
                    update_live_status(
                        True,
                        pct_d,
                        f"🔬 [{vip_tag}] 正在静默深潜详情页 ({current_overall_idx}/{total_d}: {pid}) 提取实测真动销、达人与SKU...",
                        done_d,
                        "详情页静默深潜",
                        current_overall_idx,
                        total_d,
                    )

                    success = scrape_product_detail_page(page, pid, config)
                    if success:
                        done_d += 1
                        completed_pids.append(pid)

                    # 实时写入断点进度
                    remaining_pids = pid_list[idx_p:]
                    save_deep_checkpoint({
                        "total": total_d,
                        "done_pids": completed_pids,
                        "pending_pids": remaining_pids,
                        "current_pid": pid,
                        "is_paused": False,
                    })

                    # 若还有下一款商品，执行拟人静默休眠 (8 ~ 15 秒随机)，低频低负载防风控
                    if idx_p < len(pid_list):
                        sleep_seconds = random.randint(8, 15)
                        for sec_left in range(sleep_seconds, 0, -1):
                            if check_stop_signal():
                                break
                            update_live_status(
                                True,
                                pct_d,
                                f"⏳ [{vip_tag}] 已深潜 ({current_overall_idx}/{total_d}) 款 · 拟人防风控静默休眠中 (距离下款 {sec_left}s)...",
                                done_d,
                                "详情页静默深潜",
                                current_overall_idx,
                                total_d,
                            )
                            page.wait_for_timeout(1000)

                context.close()
                clear_deep_checkpoint()
                update_live_status(
                    False,
                    100,
                    f"✅ 已完成 {done_d}/{total_d} 款精选商品详情页靶向深潜，已全维重算并解锁【👑 旗舰全维实测】评分！",
                    done_d,
                    "详情页静默深潜",
                    total_d,
                    total_d,
                    status="SUCCESS",
                )
                log_scrape_task(mode, f"静默深潜 {total_d} 款", "SUCCESS", done_d, f"✅ 完成 {done_d} 款详情页靶向深潜入库", task_id=task_id)
                return

            else:
                # batch 或 cruise (全自动无人值守变速连续翻页模式)，按「榜单 × 类目」计划依次执行，并实时写入断点
                def _save_ck(t_idx: int, next_pg: int) -> None:
                    save_checkpoint(
                        {
                            "mode": mode,
                            "plan": plan,
                            "max_pages": max_pages_per_board,
                            "task_idx": t_idx,
                            "next_page": next_pg,
                            "collected": collected_count,
                            "board_label": (
                                BOARD_LABEL_MAP.get(plan[t_idx]["board"], plan[t_idx]["board"])
                                + (f"·{plan[t_idx]['category']}" if plan[t_idx].get("category") else "")
                            ) if t_idx < len(plan) else "",
                        }
                    )

                def _handle_warning(cur_label: str, t_idx: int, cur_pg: int) -> bool:
                    w = read_plugin_warning(context)
                    if not w:
                        return False
                    _save_ck(t_idx, cur_pg)
                    if w["kind"] == "kicked":
                        tip = "原因：同一张旗舰卡在另一处（通常是您日常的 Chrome）同时在线。请 ⌘Q 完全退出日常 Chrome → 如插件提示需重新激活，在插件里重新激活卡号后再退出 Chrome → 回到本页点「⏯ 恢复上次进度」。"
                    elif w["kind"] == "rate":
                        tip = "原因：插件判定请求频率过高。请联系插件客服解封，并建议间隔一段时间后再点「⏯ 恢复上次进度」。"
                    else:
                        tip = "原因：当前网络验证失败。请更换网络后再点「⏯ 恢复上次进度」。"
                    warn_msg = f"🛡️ 插件提示【{w['title']}】，已自动停机并保存断点（本次累计入库 {collected_count} 款）。{tip}"
                    update_live_status(False, 100, warn_msg, collected_count, cur_label, cur_pg, max_pages_per_board, status="ERROR")
                    log_scrape_task(mode, cur_label, "ERROR", collected_count, warn_msg, task_id=task_id)
                    return True

                stopped = False
                for t_idx in range(start_task_idx, len(plan)):
                    if stopped or check_stop_signal():
                        stopped = True
                        break

                    b = plan[t_idx]["board"]
                    cat = plan[t_idx].get("category", "")
                    task_max = int(plan[t_idx].get("max_pages") or max_pages_per_board)
                    task_start = max(1, int(plan[t_idx].get("start_page") or 1))

                    if resume and resume_start_page is not None and t_idx == start_task_idx:
                        first_pg = max(1, resume_start_page)
                    else:
                        first_pg = task_start

                    # 确保上限不低于起始页
                    task_max = max(first_pg, task_max)

                    base_url = FASTMOSS_URLS.get(b, FASTMOSS_URLS["new"])
                    url = base_url
                    current_board_label = BOARD_LABEL_MAP.get(b, b) + (f"·{cat}" if cat else "")

                    pct = int(10 + (current_step_num / total_steps) * 75)
                    msg = f"📊 [{vip_tag}] 正在进入 [{current_board_label}] ({t_idx + 1}/{len(plan)}) 准备自动巡航抓取（目标起始第 {first_pg} 页，上限 {task_max} 页）..."
                    update_live_status(True, pct, msg, collected_count, current_board_label, current_step_num + 1, total_steps)
                    log_scrape_task(mode, current_board_label, "RUNNING", collected_count, msg, task_id=task_id)

                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    # 首次打开榜单页会产生约 30~35 次初始化 API 请求，先静置 7.5 秒消化首波 XHR 峰值
                    page.wait_for_timeout(7500)
                    if _handle_warning(current_board_label, t_idx, first_pg):
                        context.close()
                        return

                    if cat and not apply_category_filter(page, cat):
                        update_live_status(True, pct, f"ℹ️ 未在 [{BOARD_LABEL_MAP.get(b, b)}] 页面找到类目「{cat}」筛选项，跳过该组合...", collected_count, current_board_label, 0, task_max)
                        _save_ck(t_idx + 1, 1)
                        continue

                    if first_pg > 1:
                        update_live_status(True, pct, f"⏯ 正在就位起始页：[{current_board_label}] 拟人化在分页器输入第 {first_pg} 页并按回车跳转...", collected_count, current_board_label, first_pg, task_max)
                        reached = goto_list_page(page, first_pg)
                        if reached > 1:
                            first_pg = reached
                        # 若 reached <= 1（DOM 未能识别到 active 分页按钮），维持 URL 参数直达的 first_pg，绝不回退至第 1 页

                    for pg in range(first_pg, task_max + 1):
                        if check_stop_signal():
                            stopped = True
                            _save_ck(t_idx, pg)
                            break

                        # 安全检查：插件弹出 warning.html 时读取真实原因、保存断点并立即停机保护账号
                        if _handle_warning(current_board_label, t_idx, pg):
                            context.close()
                            return

                        current_step_num += 1
                        consecutive_pages_scraped += 1
                        pct = int(12 + min(80, (current_step_num / total_steps) * 78))

                        # 1. 拟人化变速分段滚动浏览（约 12 ~ 16 秒随机停留 + 触发懒加载图片，确保 60s 窗口内 XHR 远低于 90 次）
                        scroll_steps = random.randint(6, 8)
                        for s_idx in range(scroll_steps):
                            scroll_delta = random.randint(320, 520)
                            page.mouse.wheel(0, scroll_delta)
                            dwell_ms = int(random.uniform(1450, 2150))
                            page.wait_for_timeout(dwell_ms)

                        # 模拟真人视线回看顶部
                        page.mouse.wheel(0, -random.randint(1200, 1800))
                        page.wait_for_timeout(random.randint(1500, 2400))

                        update_live_status(
                            True,
                            pct,
                            f"📸 [{vip_tag} · {current_board_label}] 正在解析第 {pg} 页全量字段与极小主图 (已累计入库 {collected_count} 件)...",
                            collected_count,
                            current_board_label,
                            pg,
                            task_max,
                        )

                        dom_items = extract_products_from_dom(page, current_board_label, page_index=pg)
                        if not dom_items:
                            if _handle_warning(current_board_label, t_idx, pg):
                                context.close()
                                return
                            # 当前榜单已无更多可读行（或达到当前榜单末页），自动切换下一榜单
                            update_live_status(
                                True,
                                pct,
                                f"ℹ️ [{current_board_label}] 第 {pg} 页已无更多商品行，正自动切换下一组合...",
                                collected_count,
                                current_board_label,
                                pg,
                                task_max,
                            )
                            break

                        for item in dom_items:
                            saved = upsert_product(item, config)
                            collected_count += 1
                            if float(saved.get("potential_score", 0)) >= 85.0 and len(high_score_pids_for_deep) < 5:
                                if saved["product_id"] not in high_score_pids_for_deep:
                                    high_score_pids_for_deep.append(saved["product_id"])

                        # 每页入库后立即写入断点（下次从下一页继续）
                        _save_ck(t_idx, pg + 1)

                        msg = f"✅ [{vip_tag} · {current_board_label}] 第 {pg} 页抓取入库完成！累计已入库 {collected_count} 款墨西哥商品"
                        update_live_status(True, min(92, pct + 4), msg, collected_count, current_board_label, pg, task_max)
                        log_scrape_task(mode, current_board_label, "RUNNING", collected_count, msg, task_id=task_id)

                        if pg >= task_max:
                            break

                        # 2. 防风控波次冷却保护：每连续自动翻 4 页，自动进入 42~52 秒安全冷却休息（彻底排空 60s 滑动窗口内的 XHR 计数）
                        if consecutive_pages_scraped > 0 and consecutive_pages_scraped % 4 == 0:
                            cooldown_sec = random.randint(42, 52)
                            for rem in range(cooldown_sec, 0, -1):
                                if check_stop_signal():
                                    stopped = True
                                    break
                                update_live_status(
                                    True,
                                    pct,
                                    f"🛡️ 旗舰版插件防限流冷却休息中（已连续抓 {consecutive_pages_scraped} 页，排空60s滑动窗口剩余 {rem} 秒后继续）... 已入库 {collected_count} 件",
                                    collected_count,
                                    current_board_label,
                                    pg,
                                    task_max,
                                )
                                time.sleep(1.0)
                            if stopped:
                                break

                        # 3. 自动寻找并点击「下一页」按钮
                        next_btn = page.query_selector("li.ant-pagination-next:not(.ant-pagination-disabled)")
                        if not next_btn:
                            update_live_status(
                                True,
                                pct,
                                f"ℹ️ [{current_board_label}] 已翻至最后一页，准备切换下一组合...",
                                collected_count,
                                current_board_label,
                                pg,
                                task_max,
                            )
                            break

                        try:
                            next_btn.scroll_into_view_if_needed()
                            page.wait_for_timeout(random.randint(900, 1600))
                            next_btn.click()
                            # 翻页后拟人等待新列表加载
                            page.wait_for_timeout(random.randint(5200, 7500))
                        except Exception:
                            break

                    if stopped:
                        break
                    # 当前组合完成，断点推进到下一组合
                    _save_ck(t_idx + 1, 1)

                if stopped:
                    context.close()
                    stop_msg = f"⏹ 已安全停止并保存断点（累计入库 {collected_count} 款），可随时点「⏯ 恢复上次进度」从中断处继续。"
                    update_live_status(False, 100, stop_msg, collected_count, ",".join(boards), current_step_num, total_steps, status="SUCCESS")
                    log_scrape_task(mode, ",".join(boards), "SUCCESS", collected_count, stop_msg, task_id=task_id)
                    return

                # 全部计划完成，清除断点
                clear_checkpoint()

                # 4. 旗舰版/高分潜力品详情页二级自动下钻（对本轮最高分的 Top 3 S级新品自动进详情页保存全量快照）
                if deep and high_score_pids_for_deep and not check_stop_signal():
                    for idx_d, d_pid in enumerate(high_score_pids_for_deep[:3], 1):
                        if check_stop_signal():
                            break
                        update_live_status(
                            True,
                            95,
                            f"🔍 正在对 S级潜力爆品 ({d_pid}) 执行详情页二级深度穿透存档 ({idx_d}/{min(3, len(high_score_pids_for_deep))})...",
                            collected_count,
                            "详情页二级穿透",
                            idx_d,
                            3,
                        )
                        scrape_product_detail_page(page, d_pid, config)
                        page.wait_for_timeout(random.randint(2200, 3800))

            context.close()

        done_msg = f"🎉 自动巡航完成！本次共处理入库 {collected_count} 款墨西哥商品（含微缩主图、精准上架日期、店铺销量与全量原始 JSON 存档）"
        update_live_status(False, 100, done_msg, collected_count, ",".join(boards), total_steps, total_steps, status="SUCCESS")
        log_scrape_task(mode, ",".join(boards), "SUCCESS", collected_count, done_msg, task_id=task_id)

    except Exception as fatal_err:
        err_msg = f"⚠️ 采集结束或中断: {fatal_err}"
        update_live_status(False, 100, err_msg, collected_count, ",".join(boards), current_step_num, total_steps, status="ERROR")
        log_scrape_task(mode, ",".join(boards), "ERROR", collected_count, err_msg, task_id=task_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="batch", choices=["login", "batch", "cruise", "companion", "item", "deep_batch"])
    parser.add_argument("--boards", default="new,soaring")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--target", default="")
    parser.add_argument("--deep", action="store_true", default=True)
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--categories", default="")
    parser.add_argument("--resume", action="store_true", default=False)
    parser.add_argument("--search-pages", type=int, default=500)
    parser.add_argument("--search-start", type=int, default=1)
    parser.add_argument("--start-page", type=int, default=1)
    args = parser.parse_args()

    board_list = [x.strip() for x in args.boards.split(",") if x.strip()]
    cat_list_arg = [x.strip() for x in args.categories.split(",") if x.strip()]
    run_playwright_collector(
        args.mode,
        board_list,
        args.pages,
        args.target,
        args.deep,
        task_id=args.task_id if args.task_id > 0 else None,
        categories=cat_list_arg,
        resume=args.resume,
        search_pages=args.search_pages,
        search_start=args.search_start,
        start_page=args.start_page,
    )
