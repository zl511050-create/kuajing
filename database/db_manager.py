# -*- coding: utf-8 -*-
"""
本地私有化 SQLite 数据仓库管理层 (旗舰版全量无损存储 + 历史快照对比增强版)
支持：
1. 列表页全字段 (排名、精准上架日期、店铺名与店铺总销、店铺链接、佣金率、3日/7日/总销量与销售额)
2. 详情页二级穿透全字段 (30天日销曲线、视频/直播/商品卡渠道占比、Top5带货达人、Top5带货视频)
3. 原始数据全量快照双保险 (raw_payload_json 100% 保存网页与接口返回的全部原始字典)
4. 跨日期历史快照自动对比 (product_history_snapshots 自动计算真实销量增量与排名跃升)
"""

import datetime
import json
import os
import sqlite3
import time
from typing import Dict, Any, List, Optional
from engine.scorer import evaluate_product
from engine.taxonomy import classify_category, parse_fastmoss_product_cell_lines
from engine.es_translator import (
    translate_es_to_cn_and_1688,
    estimate_category_weight_and_cost,
    is_fake_linear_series,
    build_realistic_7d_series,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "fastmoss_hub.db")

NEW_FLAGSHIP_COLUMNS = [
    ("main_category", "TEXT DEFAULT ''"),
    ("sub_category", "TEXT DEFAULT ''"),
    ("release_date", "TEXT DEFAULT ''"),
    ("rank_num", "INTEGER DEFAULT 0"),
    ("shop_url", "TEXT DEFAULT ''"),
    ("shop_total_sales", "TEXT DEFAULT ''"),
    ("sales_3d", "INTEGER DEFAULT 0"),
    ("gmv_3d_text", "TEXT DEFAULT ''"),
    ("total_gmv_text", "TEXT DEFAULT ''"),
    ("channel_breakdown_json", "TEXT DEFAULT '{}'"),
    ("top_creators_json", "TEXT DEFAULT '[]'"),
    ("top_videos_json", "TEXT DEFAULT '[]'"),
    ("sku_specs_json", "TEXT DEFAULT '[]'"),
    ("image_large_url", "TEXT DEFAULT ''"),
    ("raw_payload_json", "TEXT DEFAULT '{}'"),
    ("deep_scraped", "INTEGER DEFAULT 0"),
    ("delta_sales", "INTEGER DEFAULT 0"),
    ("snapshot_count", "INTEGER DEFAULT 1"),
]


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(config: Dict[str, Any]) -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            title TEXT,
            title_cn TEXT,
            title_es TEXT,
            category TEXT,
            shop_name TEXT,
            shop_type TEXT DEFAULT '普通本土店',
            price_mxn REAL DEFAULT 0,
            sales_7d INTEGER DEFAULT 0,
            sales_28d INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            gmv_7d_mxn REAL DEFAULT 0,
            growth_rate_7d REAL DEFAULT 0,
            creators_7d INTEGER DEFAULT 0,
            videos_7d INTEGER DEFAULT 0,
            top_creator_share_pct REAL DEFAULT 35.0,
            product_card_share_pct REAL DEFAULT 20.0,
            days_online INTEGER DEFAULT 20,
            category_competing_shops INTEGER DEFAULT 8,
            commission_rate_pct REAL DEFAULT 12.0,
            rating REAL DEFAULT 4.7,
            review_count INTEGER DEFAULT 50,
            weight_g REAL DEFAULT 250.0,
            cost_1688_rmb REAL DEFAULT 18.0,
            supplier_1688_url TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            image_large_url TEXT DEFAULT '',
            fastmoss_url TEXT DEFAULT '',
            daily_sales_series TEXT DEFAULT '[]',
            keywords_1688 TEXT DEFAULT '[]',
            spanish_keywords TEXT DEFAULT '[]',
            target_audience TEXT DEFAULT '',
            pain_point_analysis TEXT DEFAULT '',
            video_script_angle TEXT DEFAULT '',
            potential_score REAL DEFAULT 0,
            tier TEXT DEFAULT '',
            verdict TEXT DEFAULT '',
            is_big_brand INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'LOW',
            compliance_tags TEXT DEFAULT '[]',
            radar_scores TEXT DEFAULT '{}',
            kanban_stage TEXT DEFAULT 'candidate',
            kanban_notes TEXT DEFAULT '',
            source_board TEXT DEFAULT '新品榜/飙升榜',
            updated_at TEXT
        )
        """
    )

    # 平滑升级：为已有 products 表自动补充旗舰版扩展字段
    cur.execute("PRAGMA table_info(products)")
    existing_cols = {row["name"] for row in cur.fetchall()}
    for col_name, col_def in NEW_FLAGSHIP_COLUMNS:
        if col_name not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    # 创建跨日期历史快照对比表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS product_history_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            snapshot_date TEXT,
            price_mxn REAL DEFAULT 0,
            sales_3d INTEGER DEFAULT 0,
            sales_7d INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            rank_num INTEGER DEFAULT 0,
            potential_score REAL DEFAULT 0,
            recorded_at TEXT,
            UNIQUE(product_id, snapshot_date)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            workflow_type TEXT,
            product_id TEXT DEFAULT '',
            custom_query TEXT DEFAULT '',
            report_markdown TEXT,
            ide_export_file TEXT DEFAULT '',
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scrape_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT,
            target_url_or_board TEXT,
            status TEXT,
            items_collected INTEGER DEFAULT 0,
            log_message TEXT DEFAULT '',
            created_at TEXT
        )
        """
    )

    conn.commit()

    cur.execute("SELECT COUNT(*) as cnt FROM products")
    if cur.fetchone()["cnt"] == 0:
        seed_initial_mexico_products(config)
    else:
        # 为已存在的商品补齐默认上架日期与详情链接格式
        cur.execute("SELECT product_id, days_online, release_date, fastmoss_url FROM products")
        for r in cur.fetchall():
            pid = r["product_id"]
            days = int(r["days_online"] or 15)
            rel_date = r["release_date"] or (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
            fm_url = r["fastmoss_url"] or f"https://www.fastmoss.com/zh/e-commerce/detail/{pid}"
            fm_url = fm_url.replace("/productDetail/", "/detail/")
            cur.execute(
                "UPDATE products SET release_date = ?, fastmoss_url = ? WHERE product_id = ?",
                (rel_date, fm_url, pid),
            )
        conn.commit()

    conn.close()


def upsert_product(raw_item: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    插入或更新商品（全量旗舰字段入库 + 西语品名自动汉化与1688精准词映射 + 品类真实克重估算 + 历史快照对比增量计算 + 双模自适应五维评分）
    """
    conn = get_conn()
    cur = conn.cursor()

    pid = str(raw_item.get("product_id") or f"MX-{int(time.time()*1000)}")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 查询旧记录以保留用户在看板手工填写的 1688 核价/测款状态/微缩图，并计算销量增量
    cur.execute("SELECT * FROM products WHERE product_id = ?", (pid,))
    row_exist = cur.fetchone()
    existing = dict(row_exist) if row_exist else {}

    days_online = int(raw_item.get("days_online") or existing.get("days_online") or 18)
    release_date = (
        raw_item.get("release_date")
        or existing.get("release_date")
        or (datetime.date.today() - datetime.timedelta(days=days_online)).strftime("%Y-%m-%d")
    )

    new_total_sales = int(raw_item.get("total_sales") or existing.get("total_sales") or 0)
    prev_total_sales = int(existing.get("total_sales") or new_total_sales)
    delta_sales = max(0, new_total_sales - prev_total_sales) if existing else int(raw_item.get("delta_sales") or 0)

    raw_cat_str = str(raw_item.get("sub_category") or raw_item.get("category") or existing.get("sub_category") or existing.get("category") or "")
    title_str = str(raw_item.get("title") or existing.get("title") or "Producto México")
    title_es_str = str(raw_item.get("title_es") or existing.get("title_es") or title_str)
    main_cat, sub_cat = classify_category(raw_cat_str, title_es_str)

    price_mxn = float(raw_item.get("price_mxn") or existing.get("price_mxn") or 259.0)
    ex_rate = float(config.get("profit_model", {}).get("exchange_rate_mxn_per_rmb", 2.80))

    # 1. 西语标题智能汉化 + 1688 纯中文源头厂搜索词提取
    existing_cn = str(raw_item.get("title_cn") or existing.get("title_cn") or "")
    clean_title_cn, cn_kw_1688 = translate_es_to_cn_and_1688(
        title_es=title_es_str,
        sub_category=sub_cat,
        main_category=main_cat,
        existing_title_cn=existing_cn,
    )

    # 2. 品类真实物理克重 (weight_g) 与 1688 拿货成本科学估算 (替代旧的一刀切 260g)
    cat_est = estimate_category_weight_and_cost(
        title_es=title_es_str,
        sub_category=sub_cat,
        main_category=main_cat,
        price_mxn=price_mxn,
        exchange_rate=ex_rate,
    )

    # 若旧记录是之前默认塞的 260.0g 且未进入人工核价阶段 (candidate)，自动升级为品类真实克重
    old_w = float(existing.get("weight_g") or 0)
    raw_w = float(raw_item.get("weight_g") or 0)
    if existing.get("kanban_stage") in ("sourcing", "testing", "scaling") and old_w > 0:
        final_weight_g = old_w
        final_cost_rmb = float(existing.get("cost_1688_rmb") or cat_est["cost_1688_rmb"])
    elif raw_w > 0 and raw_w != 260.0:
        final_weight_g = raw_w
        final_cost_rmb = float(raw_item.get("cost_1688_rmb") or cat_est["cost_1688_rmb"])
    elif old_w > 0 and old_w != 260.0:
        final_weight_g = old_w
        final_cost_rmb = float(existing.get("cost_1688_rmb") or cat_est["cost_1688_rmb"])
    else:
        final_weight_g = cat_est["weight_g"]
        final_cost_rmb = cat_est["cost_1688_rmb"]

    # 3. 7日动销曲线真实化重构 (消灭旧版 [0.55..1.40] 假斜线)
    final_s7 = int(raw_item.get("sales_7d") or existing.get("sales_7d") or 0)
    final_s3 = int(raw_item.get("sales_3d") or existing.get("sales_3d") or 0)
    final_growth = float(raw_item.get("growth_rate_7d") or existing.get("growth_rate_7d") or 0.0)
    cand_series = raw_item.get("daily_sales_series") or existing.get("daily_sales_series") or []
    if isinstance(cand_series, str):
        try:
            cand_series = json.loads(cand_series)
        except Exception:
            cand_series = []

    if is_fake_linear_series(cand_series):
        final_daily_series = build_realistic_7d_series(
            product_id=pid,
            sales_7d=final_s7,
            total_sales=new_total_sales,
            days_online=days_online,
            sales_3d=final_s3,
            growth_rate_7d=final_growth,
        )
    else:
        final_daily_series = [int(x) for x in cand_series]

    # 构造送入评分引擎的完整商品字典
    eval_input = dict(existing)
    eval_input.update(raw_item)
    eval_input.update({
        "title": title_str,
        "title_cn": clean_title_cn,
        "title_es": title_es_str,
        "category": sub_cat,
        "main_category": main_cat,
        "sub_category": sub_cat,
        "price_mxn": price_mxn,
        "weight_g": final_weight_g,
        "cost_1688_rmb": final_cost_rmb,
        "days_online": days_online,
        "total_sales": new_total_sales,
        "delta_sales": delta_sales,
        "daily_sales_series": final_daily_series,
    })
    eval_res = evaluate_product(eval_input, config)

    # 记录今日快照并统计历史快照次数
    try:
        cur.execute(
            """
            INSERT INTO product_history_snapshots
            (product_id, snapshot_date, price_mxn, sales_3d, sales_7d, total_sales, rank_num, potential_score, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id, snapshot_date) DO UPDATE SET
                price_mxn=excluded.price_mxn,
                sales_3d=excluded.sales_3d,
                sales_7d=excluded.sales_7d,
                total_sales=excluded.total_sales,
                rank_num=excluded.rank_num,
                potential_score=excluded.potential_score,
                recorded_at=excluded.recorded_at
            """,
            (
                pid,
                today_str,
                price_mxn,
                int(raw_item.get("sales_3d") or raw_item.get("sales_7d") or 0),
                int(raw_item.get("sales_7d") or existing.get("sales_7d") or 0),
                new_total_sales,
                int(raw_item.get("rank_num") or existing.get("rank_num") or 0),
                eval_res["potential_score"],
                now_str,
            ),
        )
        cur.execute("SELECT COUNT(*) as cnt, MIN(total_sales) as min_sales FROM product_history_snapshots WHERE product_id = ?", (pid,))
        snap_row = cur.fetchone()
        snapshot_count = int(snap_row["cnt"] or 1)
        if snapshot_count > 1 and snap_row["min_sales"] is not None:
            delta_sales = max(delta_sales, new_total_sales - int(snap_row["min_sales"]))
    except Exception:
        snapshot_count = 1

    # 合并详情页字段与原始快照 JSON
    def ensure_json_str(val: Any, default_empty: str = "[]") -> str:
        if val is None:
            return default_empty
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)

    fm_url = raw_item.get("fastmoss_url") or existing.get("fastmoss_url") or f"https://www.fastmoss.com/zh/e-commerce/detail/{pid}"
    fm_url = fm_url.replace("/productDetail/", "/detail/")

    pain_point_txt = raw_item.get("pain_point_analysis") or existing.get("pain_point_analysis") or ""
    if cat_est.get("bundle_advice") and cat_est["bundle_advice"] not in pain_point_txt:
        pain_point_txt = f"{cat_est['bundle_advice']} {pain_point_txt}".strip()

    record = {
        "product_id": pid,
        "title": title_str,
        "title_cn": clean_title_cn,
        "title_es": title_es_str,
        "category": sub_cat,
        "main_category": main_cat,
        "sub_category": sub_cat,
        "shop_name": raw_item.get("shop_name") or existing.get("shop_name") or "Tienda Local MX",
        "shop_type": raw_item.get("shop_type") or existing.get("shop_type") or "普通本土店",
        "price_mxn": price_mxn,
        "sales_7d": int(raw_item.get("sales_7d") or existing.get("sales_7d") or 0),
        "sales_28d": int(raw_item.get("sales_28d") or existing.get("sales_28d") or 0),
        "total_sales": new_total_sales,
        "gmv_7d_mxn": float(raw_item.get("gmv_7d_mxn") or existing.get("gmv_7d_mxn") or 0.0),
        "growth_rate_7d": float(raw_item.get("growth_rate_7d") or existing.get("growth_rate_7d") or 0.0),
        "creators_7d": int(raw_item.get("creators_7d") or existing.get("creators_7d") or 0),
        "videos_7d": int(raw_item.get("videos_7d") or existing.get("videos_7d") or 0),
        "top_creator_share_pct": float(raw_item.get("top_creator_share_pct") or existing.get("top_creator_share_pct") or 35.0),
        "product_card_share_pct": float(raw_item.get("product_card_share_pct") or existing.get("product_card_share_pct") or 22.0),
        "days_online": days_online,
        "category_competing_shops": int(raw_item.get("category_competing_shops") or existing.get("category_competing_shops") or 8),
        "commission_rate_pct": float(raw_item.get("commission_rate_pct") or existing.get("commission_rate_pct") or 12.0),
        "rating": float(raw_item.get("rating") or existing.get("rating") or 4.8),
        "review_count": int(raw_item.get("review_count") or existing.get("review_count") or 45),
        "weight_g": final_weight_g,
        "cost_1688_rmb": final_cost_rmb,
        "supplier_1688_url": existing.get("supplier_1688_url") or raw_item.get("supplier_1688_url") or "",
        "image_url": raw_item.get("image_url") or existing.get("image_url") or "",
        "fastmoss_url": fm_url,
        "daily_sales_series": ensure_json_str(final_daily_series, "[]"),
        "keywords_1688": ensure_json_str(cn_kw_1688, "[]"),
        "spanish_keywords": ensure_json_str(raw_item.get("spanish_keywords") or existing.get("spanish_keywords"), "[]"),
        "target_audience": raw_item.get("target_audience") or existing.get("target_audience") or "",
        "pain_point_analysis": pain_point_txt,
        "video_script_angle": raw_item.get("video_script_angle") or existing.get("video_script_angle") or "",
        "potential_score": eval_res["potential_score"],
        "tier": eval_res["tier"],
        "verdict": eval_res["verdict"],
        "is_big_brand": eval_res["is_big_brand"],
        "risk_level": eval_res["risk_level"],
        "compliance_tags": json.dumps(eval_res["compliance_tags"], ensure_ascii=False),
        "radar_scores": json.dumps(eval_res["radar_scores"], ensure_ascii=False),
        "kanban_stage": existing.get("kanban_stage") or raw_item.get("kanban_stage") or "candidate",
        "kanban_notes": existing.get("kanban_notes") or raw_item.get("kanban_notes") or "",
        "source_board": raw_item.get("source_board") or existing.get("source_board") or "墨西哥新品榜",
        "updated_at": now_str,
        # 旗舰版全量扩展字段
        "release_date": release_date,
        "rank_num": int(raw_item.get("rank_num") or existing.get("rank_num") or 0),
        "shop_url": raw_item.get("shop_url") or existing.get("shop_url") or "",
        "shop_total_sales": str(raw_item.get("shop_total_sales") or existing.get("shop_total_sales") or ""),
        "sales_3d": int(raw_item.get("sales_3d") or existing.get("sales_3d") or 0),
        "gmv_3d_text": str(raw_item.get("gmv_3d_text") or existing.get("gmv_3d_text") or ""),
        "total_gmv_text": str(raw_item.get("total_gmv_text") or existing.get("total_gmv_text") or ""),
        "channel_breakdown_json": ensure_json_str(raw_item.get("channel_breakdown_json") or existing.get("channel_breakdown_json"), "{}"),
        "top_creators_json": ensure_json_str(raw_item.get("top_creators_json") or existing.get("top_creators_json"), "[]"),
        "top_videos_json": ensure_json_str(raw_item.get("top_videos_json") or existing.get("top_videos_json"), "[]"),
        "sku_specs_json": ensure_json_str(raw_item.get("sku_specs_json") or existing.get("sku_specs_json"), "[]"),
        "image_large_url": str(raw_item.get("image_large_url") or existing.get("image_large_url") or ""),
        "raw_payload_json": ensure_json_str(raw_item.get("raw_payload_json") or existing.get("raw_payload_json"), "{}"),
        "deep_scraped": int(raw_item.get("deep_scraped") or existing.get("deep_scraped") or 0),
        "delta_sales": delta_sales,
        "snapshot_count": snapshot_count,
    }

    columns = ", ".join(record.keys())
    placeholders = ", ".join(["?"] * len(record))
    update_clause = ", ".join([f"{k}=excluded.{k}" for k in record.keys() if k != "product_id"])

    cur.execute(
        f"""
        INSERT INTO products ({columns})
        VALUES ({placeholders})
        ON CONFLICT(product_id) DO UPDATE SET {update_clause}
        """,
        list(record.values()),
    )
    conn.commit()
    conn.close()
    return record


def _deserialize_product_row(r: Dict[str, Any]) -> Dict[str, Any]:
    for list_field in [
        "daily_sales_series",
        "keywords_1688",
        "spanish_keywords",
        "compliance_tags",
        "top_creators_json",
        "top_videos_json",
        "sku_specs_json",
    ]:
        try:
            val = r.get(list_field)
            r[list_field] = json.loads(val) if isinstance(val, str) and val else (val if isinstance(val, list) else [])
        except Exception:
            r[list_field] = []
    for dict_field in ["radar_scores", "channel_breakdown_json", "raw_payload_json"]:
        try:
            val = r.get(dict_field)
            r[dict_field] = json.loads(val) if isinstance(val, str) and val else (val if isinstance(val, dict) else {})
        except Exception:
            r[dict_field] = {}
    return r


def list_products(include_big_brands: bool = True, include_raw: bool = False) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    if include_big_brands:
        cur.execute("SELECT * FROM products ORDER BY potential_score DESC, sales_7d DESC")
    else:
        cur.execute("SELECT * FROM products WHERE is_big_brand = 0 ORDER BY potential_score DESC, sales_7d DESC")
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        if not include_raw:
            d["raw_payload_json"] = "{}"
        rows.append(_deserialize_product_row(d))
    conn.close()
    return rows


def get_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return _deserialize_product_row(dict(row))


def update_product_sourcing(
    product_id: str,
    cost_1688_rmb: float,
    weight_g: float,
    price_mxn: float,
    kanban_stage: str,
    supplier_1688_url: str = "",
    kanban_notes: str = "",
) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE products
        SET cost_1688_rmb = ?, weight_g = ?, price_mxn = ?, kanban_stage = ?,
            supplier_1688_url = ?, kanban_notes = ?, updated_at = ?
        WHERE product_id = ?
        """,
        (
            float(cost_1688_rmb),
            float(weight_g),
            float(price_mxn),
            kanban_stage,
            supplier_1688_url,
            kanban_notes,
            time.strftime("%Y-%m-%d %H:%M:%S"),
            product_id,
        ),
    )
    conn.commit()
    conn.close()
    return True


def save_agent_report(report_data: Dict[str, Any], product_id: str = "", custom_query: str = "") -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO agent_reports (title, workflow_type, product_id, custom_query, report_markdown, ide_export_file, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_data.get("title", ""),
            report_data.get("workflow_type", ""),
            product_id,
            custom_query,
            report_data.get("report_markdown", ""),
            report_data.get("ide_export_file", ""),
            report_data.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S")),
        ),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def list_agent_reports(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM agent_reports ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def log_scrape_task(task_type: str, target: str, status: str, count: int, msg: str, task_id: Optional[int] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    if task_id:
        cur.execute(
            """
            UPDATE scrape_tasks
            SET status = ?, items_collected = ?, log_message = ?, created_at = ?
            WHERE id = ?
            """,
            (status, count, msg, time.strftime("%Y-%m-%d %H:%M:%S"), task_id),
        )
        rid = task_id
    else:
        cur.execute(
            """
            INSERT INTO scrape_tasks (task_type, target_url_or_board, status, items_collected, log_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_type, target, status, count, msg, time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def list_scrape_tasks(limit: int = 15) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM scrape_tasks ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def seed_initial_mexico_products(config: Dict[str, Any]) -> None:
    pass
