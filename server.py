# -*- coding: utf-8 -*-
"""
FastMoss 墨西哥私有化选品智能体中枢 · 本地 Web 服务引擎
零外部 C 扩展依赖，原生支持 Python 3.14，一键启动本地 8688 端口服务
"""

import csv
import io
import json
import os
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database.db_manager import (
    init_db,
    list_products,
    get_product_by_id,
    upsert_product,
    update_product_sourcing,
    save_agent_report,
    list_agent_reports,
    list_scrape_tasks,
    log_scrape_task,
)
from engine.profit_calc import calculate_mexico_profit, build_1688_search_links
from engine.ai_analyst import generate_workflow_report
from engine.ai_toolbox import run_toolbox_module
from scraper.fm_collector import extract_products_from_json_payload

CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")
STATIC_DIR = os.path.join(ROOT_DIR, "static")
COLLECTOR_PROC = None


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(new_cfg: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(new_cfg, f, ensure_ascii=False, indent=2)


class HubRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        # 静态资源禁用浏览器缓存，确保前端脚本修改后刷新即生效
        if not self.path.startswith("/thumbs/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(raw)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scraper/status":
            status_file = os.path.join(ROOT_DIR, "scraper", "live_status.json")
            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        self._send_json(json.load(f))
                        return
                except Exception:
                    pass
            self._send_json({"is_running": False, "status": "IDLE", "progress_pct": 0, "message": "就绪"})
            return

        if parsed.path == "/api/scraper/checkpoint":
            ck_file = os.path.join(ROOT_DIR, "scraper", "cruise_checkpoint.json")
            if os.path.exists(ck_file):
                try:
                    with open(ck_file, "r", encoding="utf-8") as f:
                        ck = json.load(f)
                    plan = ck.get("plan") or []
                    t_idx = int(ck.get("task_idx", 0))
                    self._send_json(
                        {
                            "has_checkpoint": t_idx < len(plan),
                            "board_label": ck.get("board_label", ""),
                            "task_idx": t_idx,
                            "task_total": len(plan),
                            "next_page": int(ck.get("next_page", 1)),
                            "collected": int(ck.get("collected", 0)),
                            "updated_at": ck.get("updated_at", ""),
                        }
                    )
                    return
                except Exception:
                    pass
            self._send_json({"has_checkpoint": False})
            return

        if parsed.path == "/api/scraper/deep_checkpoint":
            d_file = os.path.join(ROOT_DIR, "scraper", "deep_checkpoint.json")
            if os.path.exists(d_file):
                try:
                    with open(d_file, "r", encoding="utf-8") as f:
                        d_ck = json.load(f)
                    pending = d_ck.get("pending_pids") or []
                    done = d_ck.get("done_pids") or []
                    self._send_json(
                        {
                            "has_checkpoint": len(pending) > 0,
                            "total": int(d_ck.get("total", len(done) + len(pending))),
                            "done_count": len(done),
                            "pending_count": len(pending),
                            "current_pid": d_ck.get("current_pid", ""),
                            "is_paused": bool(d_ck.get("is_paused", False)),
                            "updated_at": d_ck.get("updated_at", ""),
                        }
                    )
                    return
                except Exception:
                    pass
            self._send_json({"has_checkpoint": False})
            return

        if parsed.path == "/api/product/raw":
            qs = parse_qs(parsed.query)
            pid = (qs.get("id") or [""])[0]
            prod = get_product_by_id(pid) if pid else None
            if prod:
                cfg = load_config()
                profit_params = cfg.get("profit_model", {})
                prod["profit_eval"] = calculate_mexico_profit(
                    prod.get("price_mxn", 299),
                    prod.get("cost_1688_rmb", 18),
                    prod.get("weight_g", 260),
                    profit_params,
                )
                prod["links_1688"] = build_1688_search_links(
                    prod.get("keywords_1688") or [prod.get("title_cn") or prod.get("title")],
                    prod.get("image_url", ""),
                )
                self._send_json({"status": "ok", "product": prod})
            else:
                self._send_json({"status": "error", "message": "未找到该商品"}, 404)
            return

        if parsed.path == "/api/dashboard":
            cfg = load_config()
            products = list_products(include_big_brands=True, include_raw=False)
            profit_params = cfg.get("profit_model", {})

            for p in products:
                p["profit_eval"] = calculate_mexico_profit(
                    p.get("price_mxn", 299),
                    p.get("cost_1688_rmb", 18),
                    p.get("weight_g", 260),
                    profit_params,
                )
                p["links_1688"] = build_1688_search_links(
                    p.get("keywords_1688") or [p.get("title_cn") or p.get("title")],
                    p.get("image_url", ""),
                )

            clean_count = sum(1 for p in products if not p.get("is_big_brand") and p.get("risk_level") != "HIGH")
            s_tier_count = sum(1 for p in products if p.get("potential_score", 0) >= 80 and not p.get("is_big_brand") and p.get("risk_level") != "HIGH")

            # 支持选品库排序参数联动 (score / sales / total_sales / newest / price_asc / price_desc)
            qs = parse_qs(parsed.query)
            sort_mode = (qs.get("sort") or ["score"])[0]

            def _to_num(val: Any) -> float:
                try:
                    return float(val or 0)
                except Exception:
                    return 0.0

            if sort_mode == "sales":
                products.sort(key=lambda x: _to_num(x.get("sales_7d")), reverse=True)
            elif sort_mode == "total_sales":
                products.sort(key=lambda x: _to_num(x.get("total_sales")), reverse=True)
            elif sort_mode == "newest":
                products.sort(key=lambda x: str(x.get("release_date") or ""), reverse=True)
            elif sort_mode == "price_asc":
                products.sort(key=lambda x: _to_num(x.get("price_mxn")))
            elif sort_mode == "price_desc":
                products.sort(key=lambda x: _to_num(x.get("price_mxn")), reverse=True)
            else:  # score
                products.sort(key=lambda x: (_to_num(x.get("potential_score")), _to_num(x.get("sales_7d"))), reverse=True)

            self._send_json(
                {
                    "status": "ok",
                    "config": cfg,
                    "kpis": {
                        "total_products": len(products),
                        "clean_candidates": clean_count,
                        "s_tier_count": s_tier_count,
                        "filtered_risk_count": len(products) - clean_count,
                    },
                    "products": products,
                    "reports": list_agent_reports(15),
                    "scrape_tasks": list_scrape_tasks(10),
                }
            )
            return

        if parsed.path == "/" or parsed.path == "":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body_raw) if body_raw else {}
        except Exception:
            payload = {}

        cfg = load_config()

        if parsed.path == "/api/agent/run":
            workflow_type = payload.get("workflow_type", "potential_discovery")
            product_id = payload.get("product_id", "")
            custom_query = payload.get("custom_query", "")

            products = list_products(include_big_brands=True)
            target_prod = get_product_by_id(product_id) if product_id else None

            res = generate_workflow_report(
                workflow_type=workflow_type,
                products=products,
                config=cfg,
                target_product=target_prod,
                custom_query=custom_query,
            )
            report_id = save_agent_report(res, product_id=product_id, custom_query=custom_query)
            res["id"] = report_id
            self._send_json({"status": "ok", "report": res})
            return

        if parsed.path == "/api/toolbox/run":
            tool_type = payload.get("tool_type", "voc_insight")
            product_id = payload.get("product_id", "")
            custom_input = payload.get("custom_input", "")

            products = list_products(include_big_brands=True)
            target_prod = get_product_by_id(product_id) if product_id else None
            res = run_toolbox_module(
                tool_type=tool_type,
                product=target_prod,
                all_products=products,
                config=cfg,
                custom_input=custom_input,
            )
            save_agent_report(
                {
                    "title": res.get("title", "AI工具箱报告"),
                    "workflow_type": f"toolbox_{tool_type}",
                    "report_markdown": res.get("report_markdown", ""),
                },
                product_id=res.get("product_id", ""),
                custom_query=custom_input,
            )
            self._send_json(res)
            return

        if parsed.path == "/api/profit/calc":
            res = calculate_mexico_profit(
                price_mxn=float(payload.get("price_mxn", 299)),
                cost_1688_rmb=float(payload.get("cost_1688_rmb", 18)),
                weight_g=float(payload.get("weight_g", 260)),
                params=payload.get("params") or cfg.get("profit_model", {}),
            )
            self._send_json({"status": "ok", "profit": res})
            return

        if parsed.path == "/api/product/update_sourcing":
            pid = str(payload.get("product_id", ""))
            if not pid:
                self._send_json({"status": "error", "message": "缺少 product_id"}, 400)
                return
            update_product_sourcing(
                product_id=pid,
                cost_1688_rmb=float(payload.get("cost_1688_rmb", 18)),
                weight_g=float(payload.get("weight_g", 260)),
                price_mxn=float(payload.get("price_mxn", 299)),
                kanban_stage=payload.get("kanban_stage", "candidate"),
                supplier_1688_url=payload.get("supplier_1688_url", ""),
                kanban_notes=payload.get("kanban_notes", ""),
            )
            # 重新评分
            prod = get_product_by_id(pid)
            if prod:
                upsert_product(prod, cfg)
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/product/add_or_import":
            items = payload.get("items") or []
            csv_text = payload.get("csv_text") or ""
            if csv_text.strip():
                reader = csv.DictReader(io.StringIO(csv_text.strip()))
                for row in reader:
                    items.append(
                        {
                            "product_id": row.get("product_id") or row.get("商品ID") or "",
                            "title_cn": row.get("title_cn") or row.get("商品名称") or row.get("title") or "",
                            "title_es": row.get("title_es") or row.get("西语标题") or row.get("title") or "",
                            "category": row.get("category") or row.get("类目") or "Hogar y Cocina",
                            "shop_name": row.get("shop_name") or row.get("店铺名称") or "Tienda MX",
                            "price_mxn": float(row.get("price_mxn") or row.get("售价") or 269),
                            "sales_7d": int(float(row.get("sales_7d") or row.get("近7天销量") or 120)),
                            "sales_28d": int(float(row.get("sales_28d") or row.get("近28天销量") or 260)),
                            "total_sales": int(float(row.get("total_sales") or row.get("总销量") or 400)),
                            "growth_rate_7d": float(row.get("growth_rate_7d") or row.get("周增长率") or 95),
                            "creators_7d": int(float(row.get("creators_7d") or row.get("关联达人") or 0)),
                            "weight_g": float(row.get("weight_g") or row.get("重量g") or 250),
                            "cost_1688_rmb": float(row.get("cost_1688_rmb") or row.get("1688拿货价") or 16),
                            "source_board": "CSV批量导入",
                        }
                    )
            count = 0
            for item in items:
                upsert_product(item, cfg)
                count += 1
            log_scrape_task("manual_import", "手动/CSV导入", "SUCCESS", count, f"成功导入并评分 {count} 款商品")
            self._send_json({"status": "ok", "imported": count})
            return

        if parsed.path == "/api/ingest_raw":
            raw_payload = payload.get("payload")
            board = payload.get("board") or "浏览器实时伴随桥接"
            extracted = extract_products_from_json_payload(raw_payload, board)
            count = 0
            for item in extracted:
                if item.get("title"):
                    upsert_product(item, cfg)
                    count += 1
            if count > 0:
                log_scrape_task("browser_bridge", board, "SUCCESS", count, f"浏览器桥接实时入库 {count} 款商品")
            self._send_json({"status": "ok", "ingested": count})
            return

        if parsed.path == "/api/scraper/checkpoint/clear":
            ck_file = os.path.join(ROOT_DIR, "scraper", "cruise_checkpoint.json")
            try:
                if os.path.exists(ck_file):
                    os.remove(ck_file)
            except Exception:
                pass
            self._send_json({"status": "ok", "message": "已清除断点"})
            return

        if parsed.path == "/api/scraper/deep_checkpoint/clear":
            d_file = os.path.join(ROOT_DIR, "scraper", "deep_checkpoint.json")
            try:
                if os.path.exists(d_file):
                    os.remove(d_file)
            except Exception:
                pass
            self._send_json({"status": "ok", "message": "已清除深潜断点"})
            return

        if parsed.path == "/api/scraper/stop":
            stop_file = os.path.join(ROOT_DIR, "scraper", "stop_signal.flag")
            with open(stop_file, "w", encoding="utf-8") as f:
                f.write("STOP")
            self._send_json({"status": "ok", "message": "已发送安全停止信号，当前页保存完成后即自动退出"})
            return

        if parsed.path == "/api/scraper/settings":
            start_page = min(500, max(1, int(payload.get("start_page", 1))))
            pages = min(500, max(1, int(payload.get("pages", 500))))
            boards = str(payload.get("boards", "search"))
            categories = str(payload.get("categories", ""))
            search_start = min(500, max(1, int(payload.get("search_start", start_page))))
            search_pages = min(500, max(1, int(payload.get("search_pages", pages))))

            cfg["scraper_settings"] = {
                "start_page": start_page,
                "pages": pages,
                "boards": boards,
                "categories": categories,
                "search_start": search_start,
                "search_pages": search_pages,
                "locked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            save_config(cfg)

            # 同时彻底清理旧断点，确保新的设定绝对生效，不被历史断点干扰
            ck_file = os.path.join(ROOT_DIR, "scraper", "cruise_checkpoint.json")
            try:
                if os.path.exists(ck_file):
                    os.remove(ck_file)
            except Exception:
                pass

            self._send_json({
                "status": "ok",
                "message": f"设定已成功锁定并保存至中枢引擎：起始第 {start_page} 页，翻页上限 {pages} 页！旧断点已清空。",
                "settings": cfg["scraper_settings"],
            })
            return

        if parsed.path == "/api/scraper/trigger":
            mode = payload.get("mode", "batch")
            saved = cfg.get("scraper_settings", {})
            boards = payload.get("boards") or saved.get("boards") or "new,soaring"
            pages = min(500, max(1, int(payload.get("pages") or saved.get("pages") or 1)))
            start_page = min(500, max(1, int(payload.get("start_page") or saved.get("start_page") or 1)))
            target = payload.get("target", "")
            categories = payload.get("categories") or saved.get("categories") or ""
            resume = bool(payload.get("resume", False))
            search_pages_val = payload.get("search_pages") or saved.get("search_pages") or pages
            search_start_val = payload.get("search_start") or saved.get("search_start") or start_page

            if not resume and mode in ("cruise", "companion", "batch"):
                # 用户开启全新抓取，主动清除历史残留断点，避免界面和调度被旧断点污染
                ck_file = os.path.join(ROOT_DIR, "scraper", "cruise_checkpoint.json")
                try:
                    if os.path.exists(ck_file):
                        os.remove(ck_file)
                except Exception:
                    pass

            # 确保前一个采集窗口已释放 browser_profile 目录锁，避免个人资料冲突弹窗
            global COLLECTOR_PROC
            if COLLECTOR_PROC and COLLECTOR_PROC.poll() is None:
                try:
                    COLLECTOR_PROC.terminate()
                except Exception:
                    pass
            try:
                if sys.platform != "win32":
                    subprocess.run(["pkill", "-f", "fm_collector.py"], check=False)
            except Exception:
                pass

            tid = log_scrape_task(mode, target or boards, "RUNNING", 0, f"正在唤醒本机 Chrome 与 Playwright ({mode})...")
            script_path = os.path.join(ROOT_DIR, "scraper", "fm_collector.py")
            cmd = [
                sys.executable,
                script_path,
                "--mode",
                mode,
                "--boards",
                boards,
                "--pages",
                str(pages),
                "--start-page",
                str(start_page),
                "--task-id",
                str(tid),
            ]
            if target:
                cmd.extend(["--target", target])
            if categories:
                cmd.extend(["--categories", categories])
            if resume:
                cmd.append("--resume")
            if search_pages_val:
                cmd.extend(["--search-pages", str(min(500, max(1, int(search_pages_val))))])
            if search_start_val:
                cmd.extend(["--search-start", str(min(500, max(1, int(search_start_val))))])

            try:
                COLLECTOR_PROC = subprocess.Popen(cmd, cwd=ROOT_DIR)
                self._send_json({"status": "ok", "message": f"已唤醒本机 Google Chrome 执行任务 ({mode})，请留意弹出的浏览器窗口！"})
            except Exception as e:
                log_scrape_task(mode, target or boards, "ERROR", 0, f"启动失败: {e}", task_id=tid)
                self._send_json({"status": "error", "message": str(e)}, 500)
            return

        if parsed.path == "/api/config/save":
            new_cfg = payload.get("config") or cfg
            save_config(new_cfg)
            # 触发全库重新评分
            for prod in list_products(include_big_brands=True):
                upsert_product(prod, new_cfg)
            self._send_json({"status": "ok"})
            return

        self._send_json({"status": "error", "message": "Unknown endpoint"}, 404)


def run_server(port: int = 8688) -> None:
    cfg = load_config()
    init_db(cfg)
    server = HTTPServer(("127.0.0.1", port), HubRequestHandler)
    print(f"============================================================")
    print(f"🇲🇽 FastMoss 墨西哥私有化选品智能体中枢已启动!")
    print(f"👉 请在浏览器打开: http://127.0.0.1:{port}")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8688
    run_server(port)
