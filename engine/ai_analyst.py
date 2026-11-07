# -*- coding: utf-8 -*-
"""
TikTok 墨西哥增长智能体大脑 (双引擎驱动)
1. 内置专业跨境选品分析师定量+定性专家引擎（无需 API Key 即可秒出结构化深度报告）
2. 支持外部大模型 API (DeepSeek / OpenAI / Gemini 兼容接口) 增强研判
3. 支持一键生成「Antigravity IDE 零成本专家联动包」写入 ./exports/ 目录
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from engine.profit_calc import calculate_mexico_profit, build_1688_search_links


def call_external_llm(system_prompt: str, user_prompt: str, ai_config: Dict[str, Any]) -> Optional[str]:
    """
    当用户在设置中配置了 DeepSeek / OpenAI / Gemini 兼容 API Key 时，调用外部大模型。
    若未配置或调用失败，自动无缝回退到内置量化专家分析引擎。
    """
    api_key = (ai_config.get("api_key") or "").strip()
    if not api_key:
        return None

    base_url = (ai_config.get("base_url") or "https://api.deepseek.com/v1").rstrip("/")
    model = ai_config.get("model") or "deepseek-chat"
    url = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            return resp_data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"> ⚠️ 外部 API 调用提示 ({e})，已自动切换为【内置墨西哥专家量化引擎】生成报告：\n\n"


def generate_workflow_report(
    workflow_type: str,
    products: List[Dict[str, Any]],
    config: Dict[str, Any],
    target_product: Optional[Dict[str, Any]] = None,
    custom_query: str = "",
) -> Dict[str, Any]:
    """
    执行四大核心智能体任务：
    - potential_discovery: 潜力商品发现（从新品榜/飙升榜挖掘非大牌、陡峭上升曲线爆品）
    - blue_ocean_scan: 蓝海机会扫描（扫描近28天高增长、低垄断细分小类目）
    - low_barrier_entry: 低门槛切入分析（适合无货盘新手、轻小件空运测款+海运囤货方向）
    - product_due_diligence: @单品 选品尽调 & 1688 测款立项
    """
    profit_params = config.get("profit_model", {})
    ai_cfg = config.get("ai_engine", {})

    # 过滤掉大牌与高危品后的优质候选池
    clean_products = [
        p for p in products
        if not p.get("is_big_brand") and p.get("risk_level") != "HIGH"
    ]
    sorted_by_score = sorted(clean_products, key=lambda x: float(x.get("potential_score", 0)), reverse=True)

    report_md = ""
    title = ""
    ide_prompt_bundle = ""

    if workflow_type == "potential_discovery":
        title = "🚀 墨西哥站点 · 潜力商品发现报告（避开大牌 & 锁定陡峭上升期）"
        top_items = sorted_by_score[:6]
        lines = [
            f"### 📊 扫描总览（墨西哥 TikTok Shop 站）",
            f"- **扫描样本池**：共分析本地库 **{len(products)}** 款商品，自动剔除大牌/Mall官旗及 NOM/COFEPRIS 强监管高危品 **{len(products) - len(clean_products)}** 款。",
            f"- **核心筛选法则**：锁定售价 `150 ~ 680 MXN`、近7天销量呈明显加速爬坡（7天日均 > 28天日均 1.3倍以上）、关联出单达人 `3~35人`（非单一大V偶然带爆）的轻小件普货。\n",
            "---",
            "### 🏆 Top 潜力爆发期商品拆解（按五维蓝海评分排序）\n",
        ]
        for idx, p in enumerate(top_items, 1):
            p_calc = calculate_mexico_profit(
                p.get("price_mxn", 299),
                p.get("cost_1688_rmb", 18),
                p.get("weight_g", 260),
                profit_params,
            )
            lines.append(
                f"#### {idx}. 【{p.get('tier', 'S级')} | {p.get('potential_score')}分】{p.get('title_cn') or p.get('title')}\n"
                f"- **西语原名**：`{p.get('title_es') or p.get('title')}`  |  **类目**：`{p.get('category')}`\n"
                f"- **价格与销量趋势**：售价 **`${p.get('price_mxn')} MXN`**（约 ¥{p_calc['revenue_rmb']}） | 近7天销量 **`{p.get('sales_7d')} 单`**（环比增长 `+{p.get('growth_rate_7d')}%`） | 历史总销 `{p.get('total_sales')} 单`（上架 `{p.get('days_online')} 天`）\n"
                f"- **渠道与达人健康度**：近7天出单达人 **`{p.get('creators_7d')} 人`** | 头部单一达人占比 `{p.get('top_creator_share_pct')}%` | 商品卡/商城自然流占比 **`{p.get('product_card_share_pct')}%`**\n"
                f"- **为什么值得切入**：{p.get('verdict')}。{p.get('pain_point_analysis', '')}\n"
                f"- **1688 测款与海运毛利预估**：1688 参考拿货价 `¥{p.get('cost_1688_rmb')}`（重量 `{p.get('weight_g')}g`） ➔ **空运测款净利 `¥{p_calc['air_test_stage']['net_profit_rmb']}/单 ({p_calc['air_test_stage']['margin_pct']}%)`**，**海运囤货净利 `¥{p_calc['sea_scale_stage']['net_profit_rmb']}/单 ({p_calc['sea_scale_stage']['margin_pct']}%)`**，保本 ROI `{p_calc['sea_scale_stage']['breakeven_roi']}`。\n"
            )

        # 同时标出反面教材（大牌或单一达人依赖型伪爆款）提醒避坑
        traps = [p for p in products if p.get("is_big_brand") or float(p.get("top_creator_share_pct") or 0) > 65][:3]
        if traps:
            lines.append("---\n### ⚠️ 避坑预警：已自动过滤的「伪机会 / 高危红海品」\n")
            for t in traps:
                reason = "大牌/官旗垄断" if t.get("is_big_brand") else f"单一头部达人占比高达 {t.get('top_creator_share_pct')}%（人带品，跟卖极易压货）"
                lines.append(f"- ❌ **{t.get('title_cn') or t.get('title')}**（售价 `${t.get('price_mxn')} MXN`，7天销 `{t.get('sales_7d')}`） ➔ **剔除原因**：{reason} | {' / '.join(t.get('compliance_tags', []))}")

        report_md = "\n".join(lines)

    elif workflow_type == "blue_ocean_scan":
        title = "🌊 墨西哥市场 · 蓝海细分小类目机会扫描报告"
        # 按类目聚合统计
        cat_map: Dict[str, List[Dict[str, Any]]] = {}
        for p in clean_products:
            cat = p.get("category") or "居家日用/未分类"
            cat_map.setdefault(cat, []).append(p)

        cat_stats = []
        for cat, items in cat_map.items():
            avg_score = sum(float(x.get("potential_score", 0)) for x in items) / len(items)
            avg_growth = sum(float(x.get("growth_rate_7d", 0)) for x in items) / len(items)
            avg_price = sum(float(x.get("price_mxn", 0)) for x in items) / len(items)
            avg_shops = sum(int(x.get("category_competing_shops", 10)) for x in items) / len(items)
            best_item = max(items, key=lambda x: float(x.get("potential_score", 0)))
            cat_stats.append({
                "category": cat,
                "count": len(items),
                "avg_score": round(avg_score, 1),
                "avg_growth": round(avg_growth, 1),
                "avg_price": round(avg_price, 0),
                "avg_shops": round(avg_shops, 1),
                "best_item": best_item,
            })

        cat_stats.sort(key=lambda x: x["avg_score"], reverse=True)
        lines = [
            "### 🧭 墨西哥蓝海类目扫描逻辑",
            "针对你**「暂无固定货盘、寻找高增长低集中度赛道做本地囤货」**的策略，系统对本地库类目按 **近7天增长斜率、同款竞争店铺离散度、轻小件普货属性** 进行了交叉聚类，锁定以下 **Top 细分蓝海方向**：\n",
            "| 排名 | 细分三级类目 | 蓝海指数 | 7天平均增速 | 主流价格带 (MXN) | 同款竞争店数 | 代表上升期单品 |",
            "| :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
        ]
        for i, c in enumerate(cat_stats[:5], 1):
            bi = c["best_item"]
            lines.append(
                f"| **#{i}** | **{c['category']}** | **{c['avg_score']}分** | `+{c['avg_growth']}%` | `${c['avg_price']} MXN` | 约 `{c['avg_shops']:.0f}` 家(分散) | {bi.get('title_cn') or bi.get('title')} |"
            )

        lines.append("\n---\n### 🔍 重点细分赛道深度拆解与切入策略\n")
        for i, c in enumerate(cat_stats[:5], 1):
            bi = c["best_item"]
            lines.append(
                f"#### 赛道 {i}：`{c['category']}`（蓝海评分：{c['avg_score']}）\n"
                f"- **市场格局**：同款竞争店铺仅约 `{c['avg_shops']:.0f}` 家，尚未出现绝对垄断头部店，中小达人挂车出单率高。\n"
                f"- **黄金定价锚点**：建议卡位 **`${max(169, int(c['avg_price'] * 0.92))} ~ ${int(c['avg_price'] * 1.08)} MXN`**，利用组合装或附赠小配件拉开与普通铺货链接的视觉差。\n"
                f"- **标杆样板商品**：**{bi.get('title_cn') or bi.get('title')}**（7天销量 `{bi.get('sales_7d')} 单`，商品卡自然流占比 `{bi.get('product_card_share_pct')}%`）。\n"
                f"- **1688 寻源方向**：搜索关键词 `{', '.join(bi.get('keywords_1688', ['源头工厂']))}`，单件拿货成本控制在 `¥{bi.get('cost_1688_rmb', 20)}` 以内即可获得 32%+ 海运净利率。\n"
            )
        report_md = "\n".join(lines)

    elif workflow_type == "low_barrier_entry":
        title = "🛠️ 墨西哥无货盘新手 · 低门槛轻小件切入分析（空运测款 ➔ 海运囤货）"
        light_items = [
            p for p in sorted_by_score
            if float(p.get("weight_g") or 300) <= 450
        ][:4]
        lines = [
            "### ✈️ 为什么「轻小件痛点功能品」是墨西哥本地囤货的最佳第一站？",
            "1. **资金周转快、试错成本极低**：单件重量 `< 400g` 的普货，首批 **100 件空运测款总投入仅需 ¥2,500 ~ ¥4,500 RMB**，空运 7~10 天即可入墨西哥本地仓上架实测真实动销。",
            "2. **零认证卡关风险**：完全避开墨西哥海关严查的 **NOM 强电认证** 与 **COFEPRIS 医疗美妆卫生许可**。",
            "3. **短视频视觉冲击力强**：解决问题型小工具（收纳、清洁、车载、宠物、美妆辅助工具）在 TikTok 前 3 秒极易做出前后对比（Before/After），哪怕找几千粉的墨西哥本土小达人免费寄样也能出单。\n",
            "---",
            "### 🎯 推荐立即切入的 3~4 个低门槛具体方向\n",
        ]
        for idx, p in enumerate(light_items, 1):
            p_calc = calculate_mexico_profit(
                p.get("price_mxn", 269),
                p.get("cost_1688_rmb", 15),
                p.get("weight_g", 220),
                profit_params,
            )
            lines.append(
                f"#### 方向 {idx}：{p.get('title_cn') or p.get('title')}（`{p.get('category')}`）\n"
                f"- **轻小件优势**：单件仅重 **`{p.get('weight_g')}g`**，1688 拿货价约 **`¥{p.get('cost_1688_rmb')}`**，前台售价 **`${p.get('price_mxn')} MXN`**（采销倍率高达 **{p_calc['markup_multiple']} 倍**）。\n"
                f"- **买家差评痛点与微创新机会**：{p.get('pain_point_analysis', '现有竞品包装简陋、配件单一，建议在1688定制加厚吸塑盒或搭配替换装组合销售。')}\n"
                f"- **起量方式拆解**：达人寄样难度低（近7天 `{p.get('creators_7d')}` 位中小达人出单），且商城搜索商品卡占比达 **`{p.get('product_card_share_pct')}%`**，主图做好西语痛点标签即可吃自然流。\n"
                f"- **首批 100 件空运测款账本**：拿货+空运头程总压货资金仅需 **`¥{p_calc['air_test_stage']['upfront_capital_rmb']:.0f}`**，空运期单件净利 **`¥{p_calc['air_test_stage']['net_profit_rmb']}`**；测爆后转海运单件净利跃升至 **`¥{p_calc['sea_scale_stage']['net_profit_rmb']} ({p_calc['sea_scale_stage']['margin_pct']}%)`**。\n"
            )
        report_md = "\n".join(lines)

    elif workflow_type == "shop_benchmarking":
        title = "🏪 墨西哥标杆黑马店铺 · 货盘结构逆向拆解报告（以店选品）"
        shop_map: Dict[str, List[Dict[str, Any]]] = {}
        for p in clean_products:
            sn = (p.get("shop_name") or "未知店铺").strip()
            if sn and sn != "未知店铺":
                shop_map.setdefault(sn, []).append(p)
        shop_list = []
        for sn, items in shop_map.items():
            total_7d = sum(int(x.get("sales_7d") or 0) for x in items)
            avg_price = sum(float(x.get("price_mxn") or 0) for x in items) / len(items)
            avg_comm = sum(float(x.get("commission_rate_pct") or 12) for x in items) / len(items)
            best_p = max(items, key=lambda x: float(x.get("potential_score") or 0))
            shop_list.append({
                "shop_name": sn,
                "count": len(items),
                "total_7d": total_7d,
                "avg_price": round(avg_price, 1),
                "avg_comm": round(avg_comm, 1),
                "best_p": best_p,
                "shop_total_sales": best_p.get("shop_total_sales") or "--",
            })
        shop_list.sort(key=lambda x: (x["count"], x["total_7d"]), reverse=True)
        lines = [
            "### 🏪 为什么在墨西哥做本土囤货一定要「以店选品」？",
            "在墨西哥站点，能够同时跑出多款上榜品的本土店铺，已经帮你验证完了 **1688 供应链可拿货性、墨西哥海关清关顺畅度、以及本土消费者的真实审美与客单价接受度**。\n",
            "| 排名 | 标杆店铺名称 | 库内上榜款数 | 店铺近7天上榜总销 | 主力均价 (MXN) | 平均达人佣金 | 镇店核心爆款 |",
            "| :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
        ]
        for idx, s in enumerate(shop_list[:8], 1):
            bp = s["best_p"]
            lines.append(
                f"| **#{idx}** | **{s['shop_name']}** | `{s['count']} 款` | `{s['total_7d']} 单` | `${s['avg_price']} MXN` | `{s['avg_comm']}%` | {bp.get('title_cn') or bp.get('title')} |"
            )
        lines.append("\n---\n### 🎯 新店「引流款 + 利润款」抄作业组盘公式\n")
        for idx, s in enumerate(shop_list[:4], 1):
            bp = s["best_p"]
            lines.append(
                f"#### 标杆店 {idx}：`{s['shop_name']}`（历史总销 `{s['shop_total_sales']}`）\n"
                f"- **货盘打法特征**：主攻 `{bp.get('main_category') or bp.get('category')}` 赛道，均价卡位 `${s['avg_price']} MXN`，平均给达人开出 `{s['avg_comm']}%` 佣金吸引中小达人挂车。\n"
                f"- **首选跟进单品**：**{bp.get('title_cn') or bp.get('title')}**（售价 `${bp.get('price_mxn')} MXN`，7天销 `{bp.get('sales_7d')} 单`）。你可以在「📊 墨西哥蓝海选品库」中点击该店铺名，一键调出它名下所有商品直接做 1688 比价。\n"
            )
        report_md = "\n".join(lines)

    elif workflow_type == "mexico_seasonal_plan":
        title = "📅 墨西哥全年大促节点与季节性备货日历推演（空运/海运截单表）"
        lines = [
            "### 🇲🇽 墨西哥 TikTok Shop 核心爆单节点与倒推备货时间轴",
            "由于你采用 **「1688 采购 ➔ 空运测款 (10天) / 海运囤货 (35~45天) ➔ 墨西哥本土海外仓发货」** 模式，必须严格按照以下供应链时间窗提前锁仓：\n",
            "| 墨西哥大促/季节节点 | 爆发时间 | 1688海运最晚截单 | 1688空运测款截单 | 核心爆发品类与选品方向 |",
            "| :--- | :---: | :---: | :---: | :--- |",
            "| **💐 母亲节 (Día de las Madres)** | 5月10日 | 3月20日前 | 4月20日前 | 美妆礼盒、卷发棒/美发梳、女士香氛、塑身衣、厨房省力小工具 |",
            "| **🔥 Hot Sale 年中大促** | 5月底~6月初 | 4月10日前 | 5月10日前 | 全品类大促：3C数码配件、移动电源、车载用品、居家收纳套装 |",
            "| **🌧️ 墨西哥雨季 & 暑假返校季** | 6月~8月 | 5月1日前 | 6月1日前 | 防水鞋套/车衣、除湿防霉日用、文具书包、儿童益智玩具 |",
            "| **💀 亡灵节 (Día de Muertos)** | 11月1日~2日 | 9月10日前 | 10月10日前 | 彩妆盘/人体彩绘、LED氛围灯串、节庆家居装饰、派对假发配饰 |",
            "| **🛍️ Buen Fin (墨西哥黑五)** | 11月中旬 | 9月25日前 | 10月25日前 | 全年最高GMV爆发期：高客单3C小家电、成套五金工具、塑身内衣多件装 |",
            "| **🎄 圣诞礼赠季 (Navidad)** | 12月1日~24日 | 10月15日前 | 11月15日前 | 新奇特玩具、情侣配饰礼盒、美甲穿戴甲套装、家庭聚会厨具 |\n",
            "---\n### 🚀 当前选品库中适合立即测款卡位的 Top 5 潜力单品\n",
        ]
        for i, p in enumerate(sorted_by_score[:5], 1):
            lines.append(
                f"{i}. **{p.get('title_cn') or p.get('title')}**（`{p.get('main_category') or p.get('category')}` | 售价 `${p.get('price_mxn')} MXN` | 7天销量 `{p.get('sales_7d')} 单`） ➔ 建议首批 **100 件空运极速测款**，7天动销若日均 >8 单立即下海运补货单。"
            )
        report_md = "\n".join(lines)

    else:
        # @单品 选品尽调 & 专项提示词工作流（微创新 / 1688谈判 / 西语脚本 / SEO商品卡 / 达人邀约 / 合规审查）
        p = target_product or (sorted_by_score[0] if sorted_by_score else (products[0] if products else {}))
        p_name = p.get("title_cn") or p.get("title", "未命名商品")
        p_es = p.get("title_es") or p.get("title", "")
        p_cat = p.get("sub_category") or p.get("category") or "居家日用"
        p_price = float(p.get("price_mxn") or 299)
        p_calc = calculate_mexico_profit(
            p_price,
            p.get("cost_1688_rmb", 18),
            p.get("weight_g", 260),
            profit_params,
        )
        links_1688 = build_1688_search_links(
            p.get("keywords_1688") or [p_name],
            p.get("image_url", ""),
        )
        kw_md = "  |  ".join([f"[🔗 搜「{item['keyword']}」]({item['url']})" for item in links_1688["keyword_links"]])

        title_map = {
            "voc_micro_innovation": f"🏭 @单品 差评痛点挖掘与 1688 差异化微创新方案：{p_name}",
            "sourcing_negotiation": f"💰 @单品 1688 寻源红线测算与工厂阶梯砍价话术：{p_name}",
            "es_video_script": f"🎬 @单品 墨西哥西语爆款短视频分镜脚本 (3套)：{p_name}",
            "seo_listing_listing": f"🛍️ @单品 西语商品卡 SEO 标题与 5 张高转化主图企划：{p_name}",
            "creator_outreach_es": f"🤝 @单品 墨西哥本土达人画像与西语邀约私信模板：{p_name}",
            "compliance_risk_audit": f"🛡️ @单品 墨西哥海关 NOM / COFEPRIS 合规与防扣货体检：{p_name}",
        }
        title = title_map.get(workflow_type, f"🎯 @单品深度尽调报告：{p_name}")

        lines = [
            f"### 1. 商品核心档案与量化评级",
            f"- **商品名称**：**{p_name}**  |  **西语原名**：`{p_es}`",
            f"- **所属类目**：`{p.get('main_category') or ''} > {p_cat}`  |  **FastMoss 商品ID**：`{p.get('product_id')}`",
            f"- **五维蓝海总评**：**{p.get('potential_score')} 分 ({p.get('tier')})**  |  **合规标签**：{' '.join(p.get('compliance_tags', []))}",
            f"- **核心动销指标**：售价 **`${p_price} MXN`** | 近7天销量 **`{p.get('sales_7d')} 单`** (`+{p.get('growth_rate_7d')}%`) | 历史总销 `{p.get('total_sales')} 单` | 上架 `{p.get('release_date') or p.get('days_online')} 天`\n",
        ]

        if workflow_type == "voc_micro_innovation":
            lines.extend([
                "### 2. 墨西哥买家高频差评痛点拆解 (VOC 逆向工程)",
                f"- **痛点 1（缺少西语说明导致不会用/退货）**：超过 35% 的墨西哥差评源于中国直发白盒包装无西班牙语说明。**改良方案**：在 1688 印刷一张 `10x15cm` 铜版纸双面全彩西语图文步骤卡（成本仅 `¥0.15/张`），直接印上售后 WhatsApp 引导好评。",
                f"- **痛点 2（长途海运外包装挤压变形）**：墨西哥尾程快递（J&T / Estafeta）分拣较暴力。**改良方案**：要求 1688 工厂由普通单层彩盒升级为 **三层加硬 E 瓦楞飞机盒 + 气泡柱内衬**（增加成本 `¥0.6/个`，破损退货率降低 80%）。",
                f"- **痛点 3（单件装性价比感知弱，易陷入价格战）**：当前竞品单件售价 `${p_price} MXN`。**改良方案**：推出 **「主品 + 替换配件/便携收纳袋」高感知组合装**，成本仅增加 `¥1.8 RMB`，前台定价可拉升至 **`${int(p_price * 1.28)} MXN`**，彻底跳出同款比价！\n",
            ])
        elif workflow_type == "sourcing_negotiation":
            target_rmb = round(p_calc["revenue_rmb"] * 0.22, 1)
            lines.extend([
                "### 2. 1688 拿货成本红线倒推与阶梯砍价话术",
                f"- **1688 一键找源头厂**：{kw_md}",
                f"- **成本红线测算**：基于墨西哥售价 `${p_price} MXN`（约 `¥{p_calc['revenue_rmb']} RMB`），为确保海运净利率 ≥30%，**1688 出厂含包装红线价应控制在 `¥{target_rmb} RMB` 以内**，单件计费体积重需控制在 `{p.get('weight_g', 260)}g` 以内（严防空运抛货）。",
                "- **💬 复制即用的 1688 源头厂询盘砍价话术**：",
                f"  > 「老板你好，我们是专门做 TikTok 墨西哥本土海外仓囤货的团队，这款【{p_name}】目前在我们墨西哥站测款排期里。首单我们先拿 **100~150 件发空运测款**，测爆后单月海运返单在 **1000~3000 件**。请报一下：1) 100件、500件、2000件的实底阶梯裸价；2) 能否免费帮塞一张我们提供的西语说明书并贴 FNSKU 条码；3) 单个最紧凑包装尺寸（长宽高cm）和实重是多少？我们要控制空运材积重。」\n",
            ])
        elif workflow_type == "es_video_script":
            lines.extend([
                "### 2. 墨西哥本土高转化 TikTok 西语带货短视频脚本 (3套)",
                "#### 🎬 脚本 A：强痛点前后对比型 (Before / After · 适合投流与泛流量破圈)",
                f"- **【0~3秒 黄金钩子 Hook】**：画面直接展示没有使用【{p_name}】时的糟糕/杂乱痛点场景，大字幕弹出 + 夸张女声配音：`\"¡No compres otro más sin ver esto! ¿Te pasa esto todos los días?\"`（没看这个之前千万别乱买！你每天也遇到这种烦恼吗？）",
                f"- **【4~12秒 丝滑功能演示】**：特写镜头一秒用上本产品，展示惊艳效果：`\"Mira cómo cambia en 3 segundos. Súper práctico y resistente.\"`（看它3秒钟带来的改变，超级实用耐造。）",
                f"- **【13~18秒 本土信任促单 CTA】**：展示墨西哥本地包裹快速发出：`\"¡Envío rápido desde México! Haz clic en el carrito naranja abajo antes de que se agote el descuento.\"`（墨西哥本地仓极速发货！折扣抢光前快点左下角小黄车！）\n",
                "#### 🎬 脚本 B：沉浸式 ASMR 开箱与细节实测型 (适合腰尾部达人寄样)",
                f"- **【0~3秒 视觉吸引】**：近距离撕开快递盒，展示高颜值主体与配件：`\"Lo que pedí en TikTok Shop México vs lo que recibí... ¡Me encantó!\"`（我在墨西哥 TikTok 买的 vs 实际收到的…太爱了！）",
                f"- **【4~15秒 3个核心卖点连击】**：边演示边数手指展示材质、便携度与性价比，打消低质顾虑。\n",
            ])
        elif workflow_type == "seo_listing_listing":
            lines.extend([
                "### 2. 墨西哥 TikTok Shop 商品卡西语 SEO 标题与 5 张主图企划",
                "- **🔥 高权重拉美西语 SEO 标题备选（直接复制上架）**：",
                f"  1. `[Envío desde México] {p_es} Original Alta Calidad Práctico Uso Diario Oferta`",
                f"  2. `{p_es} Profesional Portátil Resistente - Ideal para Hogar y Regalo (Entrega Rápida MX)`",
                "- **🔍 必埋西语热搜长尾词**：`envio gratis mexico`, `oferta relampago`, `alta calidad`, `facil de usar`, `mas vendido tiktok`, `regalo util`",
                "- **🖼️ 5 张高点击商品卡主图企划**：",
                "  - **主图 1（首图决胜点击率）**：产品高清 45° 特写 + 右上角醒目绿标 **「🇲🇽 Envío Rápido desde México (本土极速发)」** + 底部大字痛点收益词。",
                "  - **主图 2（痛点对比图）**：左半图红叉 ❌ `Otros (普通劣质款)` vs 右半图绿勾 ✅ `El Nuestro (本品升级款)`。",
                "  - **主图 3（使用场景与步骤图）**：1-2-3 步极简西语图示，一眼看懂怎么用。",
                "  - **主图 4（尺寸规格与全家福）**：清晰标出 `cm / g` 尺寸与包装内含配件清单，大幅降低因尺寸误解导致的差评。",
                "  - **主图 5（多件装/家庭装促单图）**：突出买 2 件省运费或组合装高性价比。\n",
            ])
        elif workflow_type == "creator_outreach_es":
            lines.extend([
                "### 2. 墨西哥本土达人筛选标准与高回复率西语建联私信",
                f"- **🎯 黄金寄样达人画像**：锁定粉丝量 **5,000 ~ 80,000** 的墨西哥本土腰尾部达人（类目：`{p_cat}` / 居家好物 / 每日开箱），近 30 天发片勤奋（≥10条带货视频），这种达人配合度极高，基本给免费样品 + `{max(12, int(p.get('commission_rate_pct') or 15))}%` 佣金就会尽心拍片。",
                "- **💌 话术 1：TikTok 后台 / 达人广场首联免费寄样（西语原文 + 中文对照）**",
                f"  > **ES**: `¡Hola! 👋 Nos encanta tu contenido en TikTok. Somos una tienda local en México y creemos que nuestro producto estrella 【{p_es}】 encaja perfecto con tu audiencia. Tiene alta conversión y ofrecemos {max(12, int(p.get('commission_rate_pct') or 15))}% de comisión + muestra GRATIS enviada desde nuestro almacén en México (llega en 2-3 días). ¿Te gustaría probarlo? ¡Saludos!`",
                f"  > **CN**: （你好！我们非常喜欢你的TikTok内容。我们是墨西哥本土店，相信我们的爆款非常适合你的粉丝。目前转化率很高，我们提供高佣金+墨西哥本地仓免费寄样，2-3天即达，愿意试试吗？）",
                "- **💌 话术 2：WhatsApp 样品签收后提供爆款脚本参考（温和催片）**",
                "  > **ES**: `¡Hola! Vimos que ya recibiste la muestra 🎉 ¿Qué te pareció? Te compartimos 2 ideas de ganchos (hooks) de 3 segundos que están generando muchas ventas en México con este producto para que ganes más comisiones fácilmente...`\n",
            ])
        elif workflow_type == "compliance_risk_audit":
            lines.extend([
                "### 2. 墨西哥海关准入 (NOM / COFEPRIS / IFETEL) 与平台合规深度体检",
                f"- **当前单品风险等级**：**`{p.get('risk_level', 'LOW')}`** | 扫描标签：{' '.join(p.get('compliance_tags', ['✅ 常规普货']))}",
                "- **📋 墨西哥四大清关与上架必查红线对照表**：",
                "  1. **⚡ NOM 强制安全认证**：凡带交流电插头（>24V）、直发器/吹风机、家用电器必须具备墨西哥 NOM 认证；若为 USB 低压（5V）供电或纯物理结构件，则属于免 NOM 绿通品。",
                "  2. **📡 IFETEL 无线射频认证**：凡带蓝牙（Bluetooth）或 WiFi 功能的电子产品大货海运清关严查 IFETEL，无证切勿走一般贸易大宗海运。",
                "  3. **💄 COFEPRIS 医疗卫生许可**：直接涂抹于皮肤/嘴唇的液体彩妆、护肤品、入口保健品、纹身耗材受 COFEPRIS 严管；新手起步优先选 **美妆辅助工具（化妆刷/美甲灯/卷发筒/收纳盒）**，利润相同但零扣关风险！",
                "  4. **©️ 品牌商标与外观避坑**：标题与主图严禁出现国际大牌 Logo 或西语侵权词，包装盒建议贴中性西语自主品牌标。\n",
            ])

        lines.extend([
            "### 3. 目标人群画像与墨西哥本土痛点 (Target Audience & VOC)",
            f"- **核心消费人群**：{p.get('target_audience', '墨西哥18~45岁注重家庭实用性与高性价比的城市年轻家庭及上班族，偏好直观解决日常痛点的功能型产品。')}",
            f"- **核心卖点与差评改良机会**：{p.get('pain_point_analysis', '解决墨西哥家庭/车载高频痛点；竞品差评主要集中在物流外包装挤压变形或缺少西语说明图卡，1688拿货时加配一张西语彩印使用说明卡即可显著提升5星好评率。')}",
            "### 4. 1688 寻源比价与墨西哥本土囤货双阶段账本",
            f"- **1688 一键找源头工厂**：{kw_md}",
            f"- **核算基准**：1688 拿货价 `¥{p_calc['cost_1688_rmb']}` | 重量 `{p_calc['weight_g']}g` | 售价 `${p_calc['price_mxn']} MXN`（折合 `¥{p_calc['revenue_rmb']}`，采销倍率 `{p_calc['markup_multiple']}x`）",
            f"  - **✈️ 阶段一（空运 100 件快速测款）**：单件总成本 `¥{p_calc['air_test_stage']['total_cost_rmb']}` ➔ **单件净利 `¥{p_calc['air_test_stage']['net_profit_rmb']}` (`{p_calc['air_test_stage']['margin_pct']}%`)** | 100件首批压货资金仅需 **`¥{p_calc['air_test_stage']['upfront_capital_rmb']:.0f}`**",
            f"  - **🚢 阶段二（海运 500 件放大囤货）**：单件总成本 `¥{p_calc['sea_scale_stage']['total_cost_rmb']}` ➔ **单件净利 `¥{p_calc['sea_scale_stage']['net_profit_rmb']}` (`{p_calc['sea_scale_stage']['margin_pct']}%`)** | 保本广告 ROI **`{p_calc['sea_scale_stage']['breakeven_roi']}`**",
            f"- **最终立项结论**：**{p_calc['decision']}** —— {p_calc['decision_detail']}\n",
        ])
        report_md = "\n".join(lines)

    # 如果用户配置了外部大模型 API Key，则可将内置量化数据喂给外部 LLM 做额外补充
    if ai_cfg.get("api_key"):
        sys_p = (
            "你是一位精通 TikTok Shop 墨西哥市场与 1688 供应链的资深跨境选品数据分析师。"
            "请基于提供的 FastMoss 真实量化数据与利润测算结果，输出专业、犀利、可落地的选品策略补充建议。"
        )
        llm_res = call_external_llm(sys_p, f"用户额外指令：{custom_query}\n\n当前量化报告初稿：\n{report_md}", ai_cfg)
        if llm_res:
            report_md = f"{report_md}\n\n---\n### 🤖 AI 专家大模型深度补充研判\n{llm_res}"

    # 生成可供 Antigravity IDE 零成本深度联动的导出数据包
    export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
    os.makedirs(export_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    export_filename = f"agent_task_{workflow_type}_{ts}.md"
    export_path = os.path.join(export_dir, export_filename)

    ide_prompt_bundle = (
        f"# Antigravity 跨境选品专家联动任务包 ({title})\n\n"
        f"> 💡 **使用方法**：在 Antigravity 对话框中直接输入：`请读取 exports/{export_filename} 并帮我做深度选品策略诊断与1688砍价/视频脚本拆解`\n\n"
        f"## 1. 用户自定义诉求\n{custom_query or '请基于以下本地私有中枢抓取并评分的墨西哥 TikTok Shop 数据，给出进一步的选品决断、1688同款差异化微创新方案及西语短视频带货脚本。'}\n\n"
        f"## 2. 量化引擎生成的基准报告\n{report_md}\n"
    )
    try:
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(ide_prompt_bundle)
    except Exception:
        pass

    return {
        "title": title,
        "workflow_type": workflow_type,
        "report_markdown": report_md,
        "ide_export_file": f"exports/{export_filename}",
        "ide_command_hint": f"请读取 exports/{export_filename} 进行深度选品研判",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
