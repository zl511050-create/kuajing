# -*- coding: utf-8 -*-
"""
墨西哥 TikTok Shop 五维蓝海潜力评分与红线过滤引擎 (V2.0 残酷实战 & 标准版/旗舰版双模自适应版)
核心特性：
1. 【标准版 ⇄ 旗舰版自动感知切换】：
   - 标准版模式 (STANDARD_ADAPTIVE)：当网页列表受权限限制缺失达人明细/28天日销时，绝不用假默认值刷高分，
     而是以「真实日均动销速度 (Velocity)、新品爆发锐度、3PL尾程净利安全度、佣金吸引力」为核心拉开正态分布区分度。
   - 旗舰版/深潜模式 (FLAGSHIP_VERIFIED)：当升级旗舰版或执行「🔬 详情页靶向深潜」捕获到真实每日曲线、
     达人出单分布、头部达人集中度与商品卡自然流占比时，自动解锁全维高精度评分模型与 95+ 顶级上限！
2. 【墨西哥 3PL 本土尾程刺客熔断 (< $130 MXN)】：
   - 低于 $130 MXN 的单品扣除 30 MXN 尾程与佣金后单买必亏，自动降级并提示「需多件捆绑售卖」。
3. 【80+ 国际/拉美大牌与 IP 侵权黑名单 + COFEPRIS 口服保健/涂抹美妆严管拦截】。
"""

import json
import re
from typing import Dict, Any, List


EXTENDED_BRAND_BLACKLIST = [
    "xiaomi", "redmi", "apple", "iphone", "AirPods", "samsung", "galaxy", "sony", "lg ",
    "philips", "dyson", "lenovo", "hp ", "dell", "asus", "acer", "huawei", "honor", "oppo", "vivo", "realme",
    "anker", "ugreen", "baseus", "jbl", "bose", "logitech", "razer", "nintendo", "playstation", "xbox",
    "nike", "adidas", "puma", "reebok", "under armour", "new balance", "converse", "vans", "crocs", "skechers",
    "zara", "shein", "h&m", "uniqlo", "levi's", "levis", "calvin klein", "tommy hilfiger", "victoria's secret",
    "loreal", "l'oréal", "maybelline", "nyx", "garnier", "cerave", "la roche-posay", "la roche", "vichy",
    "neutrogena", "olay", "nivea", "dove", "pantene", "head & shoulders", "tresemme", "revlon", "mac ",
    "estee lauder", "clinique", "lancome", "dior", "chanel", "gucci", "prada", "versace", "armani", "ysl",
    "e.l.f.", "elf ", "the ordinary", "bioderma", "avene", "cetaphil", "vaseline", "gillette", "oral-b",
    "colgate", "listerine", "johnson", "pampers", "huggies", "nestle", "mattel", "hasbro", "lego",
    "disney", "marvel", "spiderman", "avengers", "star wars", "rayo mcqueen", "pixar", "hello kitty",
    "sanrio", "kuromi", "barbie", "hot wheels", "pokemon", "pokémon", "naruto", "dragon ball",
    "oster", "black+decker", "black & decker", "deWalt", "bosch", "makita", "stanley", "truper", "t-fal", "tefal",
]

EXTENDED_COFEPRIS_KEYWORDS = [
    "probióticos", "probioticos", "gomitas", "suplemento", "cápsulas", "capsulas", "vitamina",
    "colágeno", "colageno", "cortisol", "drenaje linfático", "inositol", "melatonina", "proteína",
    "creatina", "quemador de grasa", "bajar de peso", "adelgazante", "medicamento", "pomada",
    "bálsamo labial", "balsamo labial", "labiales", "labial", "crema exfoliante", "suero facial",
    "ácido hialurónico", "retinol", "protector solar", "perfume", "fragancia", "aceite de argán",
    "tinte para cabello", "lentes de contacto", "jeringa", "termómetro médico",
    "保健食品", "保健", "益生菌", "软糖", "胶囊", "口服", "减肥", "口红", "唇彩", "唇釉", "香水", "面霜", "精华",
]

EXTENDED_NOM_KEYWORDS = [
    "2200w", "1800w", "1500w", "1200w", "110v", "220v", "enchufe", "corriente alterna",
    "secador de pelo", "secadora de cabello", "plancha de cabello", "plancha de vapor",
    "freidora de aire", "licuadora eléctrica", "microondas", "cafetera eléctrica", "calentador eléctrico",
    "插电", "高压", "吹风机", "电吹风", "直发器", "卷、直发器", "空气炸锅", "电磁炉",
]


def _is_flagship_or_deep_verified(product: Dict[str, Any]) -> bool:
    """
    判断当前商品是否拥有「旗舰版 / 详情页深潜实测」级别的数据完整度。
    """
    if int(product.get("deep_scraped") or 0) == 1:
        return True
    if int(product.get("snapshot_count") or 1) >= 2:
        return True

    # 检查是否有真实的非默认达人或视频 JSON
    tc = product.get("top_creators_json")
    tv = product.get("top_videos_json")
    if tc and tc not in ("[]", "", None):
        return True
    if tv and tv not in ("[]", "", None):
        return True

    # 检查 creators_7d 是否不是列表页硬塞的默认值 8
    creators_7d = int(product.get("creators_7d") or 0)
    if creators_7d > 0 and creators_7d != 8:
        return True

    return False


def evaluate_product(product: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    对单个商品执行：
    1. 80+ 国际大牌/IP侵权黑名单与官旗店检测
    2. 墨西哥 NOM 强电 / COFEPRIS 口服保健与涂抹美妆合规风险检测
    3. < $130 MXN 本土 3PL 尾程刺客亏损熔断检测
    4. 标准版自适应 (STANDARD_ADAPTIVE) ⇄ 旗舰版全维精准 (FLAGSHIP_VERIFIED) 双模五维量化评分
    """
    rules = config.get("selection_rules", {})
    title = str(product.get("title", "") or "")
    title_cn = str(product.get("title_cn", "") or "")
    title_es = str(product.get("title_es", "") or "")
    category = str(product.get("category", "") or "")
    sub_cat = str(product.get("sub_category", "") or "")
    main_cat = str(product.get("main_category", "") or "")
    shop_name = str(product.get("shop_name", "") or "")
    shop_type = str(product.get("shop_type", "") or "普通本土店")
    full_text = f"{title} {title_cn} {title_es} {category} {sub_cat} {main_cat} {shop_name}".lower()

    is_flagship_data = _is_flagship_or_deep_verified(product)
    data_tier_label = "👑 旗舰全维实测" if is_flagship_data else "📊 标准版自适应建模"

    # 1. 大牌、IP侵权与官旗店过滤
    cfg_brands = [b.lower() for b in rules.get("brand_blacklist", [])]
    all_brands = list(set(cfg_brands + [b.lower() for b in EXTENDED_BRAND_BLACKLIST]))
    matched_brands = []
    for b in all_brands:
        if len(b.strip()) <= 3:
            if re.search(r"\b" + re.escape(b.strip()) + r"\b", full_text):
                matched_brands.append(b.strip())
        elif b in full_text:
            matched_brands.append(b.strip())

    is_mall = (
        "mall" in shop_type.lower()
        or "旗舰" in shop_type
        or "oficial" in shop_name.lower()
        or "official" in shop_name.lower()
    )
    is_big_brand = bool(matched_brands) or is_mall

    # 2. 墨西哥 NOM / COFEPRIS 合规与物流风险扫描
    cfg_nom = rules.get("nom_high_risk_keywords", []) + EXTENDED_NOM_KEYWORDS
    cfg_cofepris = rules.get("cofepris_high_risk_keywords", []) + EXTENDED_COFEPRIS_KEYWORDS
    lightweight_hits = [kw for kw in rules.get("lightweight_preferred_keywords", []) if kw.lower() in full_text]

    nom_risks = [kw for kw in cfg_nom if kw.lower() in full_text]
    cofepris_risks = [kw for kw in cfg_cofepris if kw.lower() in full_text]

    # 特例豁免：美甲打磨机/工具、化妆刷、卷发筒（sin calor）、假发属于美妆工具而非液体涂抹化妆品
    if any(k in full_text for k in ["lima eléctrica", "sin calor", "brochas", "pestañas", "peluca", "假发", "美甲工具"]):
        cofepris_risks = []

    est_weight_g = float(product.get("weight_g") or 210.0)
    price_mxn = float(product.get("price_mxn") or 0)
    is_low_price_trap = 0 < price_mxn < 130.0

    compliance_tags = []
    risk_level = "LOW"  # LOW, MEDIUM, HIGH

    if is_big_brand:
        b_hint = matched_brands[0].upper() if matched_brands else "官旗"
        compliance_tags.append(f"🚫 大牌/IP侵权({b_hint}·避开)")
        risk_level = "HIGH"
    if nom_risks:
        compliance_tags.append("⚠️ 涉NOM强电认证风险")
        risk_level = "HIGH"
    if cofepris_risks:
        compliance_tags.append("⚠️ 涉COFEPRIS保健/美妆许可")
        risk_level = "HIGH"
    if is_low_price_trap:
        compliance_tags.append(f"💸 低客单尾程刺客(${price_mxn:.0f}<$130·需捆绑多件卖)")
        if risk_level == "LOW":
            risk_level = "MEDIUM"
    if est_weight_g > 900:
        compliance_tags.append(f"⚠️ 偏重件({est_weight_g:.0f}g·优先走海运)")
        if risk_level == "LOW":
            risk_level = "MEDIUM"
    if not is_big_brand and not nom_risks and not cofepris_risks and not is_low_price_trap and est_weight_g <= 550:
        compliance_tags.append("✅ 黄金轻小件普货(免认证·高毛利)")

    # ---------------------------------------------------------
    # 维度 1：销量爆发斜率与真实动销速度 S_momentum (满分 100，权重 35%)
    # ---------------------------------------------------------
    sales_3d = float(product.get("sales_3d") or 0)
    sales_7d = float(product.get("sales_7d") or sales_3d or 0)
    total_sales = float(product.get("total_sales") or sales_7d)
    days_online = max(1, int(product.get("days_online") or 20))
    delta_sales = int(product.get("delta_sales") or 0)

    # 核心指标 A：真实有效日均销量 (Effective Daily Velocity)
    active_window = min(7, days_online)
    avg_daily_7d = sales_7d / max(1.0, float(active_window))
    lifetime_daily = total_sales / max(1.0, float(days_online))
    acceleration_ratio = avg_daily_7d / max(0.5, lifetime_daily)

    # 核心指标 B：新品近期销量集中度 (New Burst Ratio = 近7天销量 / 总销量)
    burst_ratio = min(1.0, sales_7d / max(1.0, total_sales))

    # 基于真实日均单量的阶梯打分（严格拉开差距，拒绝全员高分）
    if avg_daily_7d >= 80:
        vel_score = 52.0
    elif avg_daily_7d >= 40:
        vel_score = 44.0
    elif avg_daily_7d >= 20:
        vel_score = 36.0
    elif avg_daily_7d >= 10:
        vel_score = 26.0
    elif avg_daily_7d >= 4:
        vel_score = 16.0
    else:
        vel_score = 8.0

    # 加速度与新品爆发加成
    accel_bonus = min(22.0, max(0.0, acceleration_ratio * 11.0))
    burst_bonus = burst_ratio * 14.0 if days_online <= 35 else burst_ratio * 6.0

    # 旗舰版/深潜实测日销序列或跨次采集增量加成
    flagship_curve_bonus = 0.0
    if is_flagship_data:
        daily_series = product.get("daily_sales_series") or []
        if isinstance(daily_series, str):
            try:
                daily_series = json.loads(daily_series)
            except Exception:
                daily_series = []
        if len(daily_series) >= 5:
            diffs = [daily_series[i] - daily_series[i - 1] for i in range(1, len(daily_series))]
            pos_days = sum(1 for d in diffs if d > 0)
            flagship_curve_bonus += (pos_days / len(diffs)) * 12.0
    if delta_sales > 0:
        flagship_curve_bonus += min(10.0, delta_sales / 5.0)

    s_momentum = min(100.0, vel_score + accel_bonus + burst_bonus + flagship_curve_bonus)

    # ---------------------------------------------------------
    # 维度 2：达人带货健康度与佣金激励度 S_creator (满分 100，权重 20%)
    # ---------------------------------------------------------
    creators_7d = int(product.get("creators_7d") or product.get("creator_count") or 0)
    top_creator_share = float(product.get("top_creator_share_pct") or 35.0)
    mall_card_share = float(product.get("product_card_share_pct") or 22.0)
    comm_rate = float(product.get("commission_rate_pct") or 12.0)

    if is_flagship_data:
        # 旗舰版/深潜模式：拥有真实达人矩阵与商品卡占比数据
        if 4 <= creators_7d <= 40:
            c_cnt_score = 50.0
        elif creators_7d > 40:
            c_cnt_score = 34.0
        elif 1 <= creators_7d <= 3:
            c_cnt_score = 26.0
        else:
            c_cnt_score = 18.0

        if top_creator_share <= 45.0:
            conc_score = 30.0
        elif top_creator_share <= 65.0:
            conc_score = 16.0
        else:
            conc_score = 4.0

        card_bonus = min(20.0, max(4.0, mall_card_share * 0.7))
        s_creator = min(100.0, c_cnt_score + conc_score + card_bonus)
    else:
        # 标准版自适应模式：不给假满分，基于真实公开佣金率 + 动销规模推演达人意愿度（封顶 78 分，留出深潜上升空间）
        if comm_rate >= 18:
            comm_score = 42.0
        elif comm_rate >= 14:
            comm_score = 36.0
        elif comm_rate >= 10:
            comm_score = 30.0
        else:
            comm_score = 22.0
        vol_trust = min(34.0, (sales_7d / 12.0))
        s_creator = min(78.0, comm_score + vol_trust)

    # ---------------------------------------------------------
    # 维度 3：蓝海非垄断度与生命周期位置 S_blue_ocean (满分 100，权重 20%)
    # ---------------------------------------------------------
    competing_shops = int(product.get("category_competing_shops") or 8)

    # 最佳切入窗口：总销在 60 ~ 4,500 单之间（已验证市场需求，但尚未形成万单绝对垄断）
    if 80 <= total_sales <= 2500:
        vol_score = 52.0
    elif 2500 < total_sales <= 6500:
        vol_score = 38.0
    elif 25 <= total_sales < 80:
        vol_score = 34.0
    elif total_sales > 10000:
        vol_score = 12.0  # 万单老链接，跟卖难度极高
    else:
        vol_score = 20.0

    # 上架新鲜度（新品榜精准抓取了 release_date）
    if days_online <= 14:
        fresh_score = 32.0
    elif days_online <= 30:
        fresh_score = 24.0
    elif days_online <= 60:
        fresh_score = 15.0
    else:
        fresh_score = 6.0

    comp_score = 16.0 if competing_shops <= 15 else max(4.0, 16.0 - (competing_shops - 15) * 0.5)
    s_blue_ocean = min(100.0, vol_score + fresh_score + comp_score)

    # ---------------------------------------------------------
    # 维度 4：轻小件物流与墨西哥海关合规适配度 S_logistics (满分 100，权重 15%)
    # ---------------------------------------------------------
    if est_weight_g <= 180:
        s_logistics = 94.0
    elif est_weight_g <= 320:
        s_logistics = 86.0
    elif est_weight_g <= 500:
        s_logistics = 74.0
    elif est_weight_g <= 800:
        s_logistics = 56.0
    else:
        s_logistics = 35.0

    if lightweight_hits:
        s_logistics = min(100.0, s_logistics + 6.0)
    if nom_risks or cofepris_risks:
        s_logistics = max(8.0, s_logistics - 58.0)

    # ---------------------------------------------------------
    # 维度 5：墨西哥 3PL 本土仓黄金客单价带 S_price (满分 100，权重 10%)
    # ---------------------------------------------------------
    min_p = float(rules.get("min_price_mxn", 150.0))
    max_p = float(rules.get("max_price_mxn", 680.0))

    if 180.0 <= price_mxn <= 580.0:
        s_price = 98.0  # 最佳利润甜区：扣除 30 MXN 尾程后毛利极丰厚，且墨西哥买家无需分期即可冲动下单
    elif min_p <= price_mxn < 180.0 or 580.0 < price_mxn <= max_p:
        s_price = 84.0
    elif 130.0 <= price_mxn < min_p or max_p < price_mxn <= 950.0:
        s_price = 62.0
    elif 90.0 <= price_mxn < 130.0:
        s_price = 25.0  # 尾程刺客预警区
    else:
        s_price = 10.0  # < 90 MXN 严重亏损区 或 > 950 MXN 超高客单滞销区

    # ---------------------------------------------------------
    # 综合加权总分与红线熔断惩罚
    # ---------------------------------------------------------
    total_score = (
        0.35 * s_momentum
        + 0.20 * s_creator
        + 0.20 * s_blue_ocean
        + 0.15 * s_logistics
        + 0.10 * s_price
    )

    # 熔断 1：低客单尾程刺客 (< $130 MXN) 强制扣分降级
    if is_low_price_trap:
        penalty = 22.0 if price_mxn < 85.0 else 15.0
        total_score = max(28.0, total_score - penalty)

    # 熔断 2：国际大牌 / IP侵权 一票否决
    if is_big_brand:
        total_score = min(total_score * 0.45, 44.0)
    # 熔断 3：NOM 强电 / COFEPRIS 口服保健与涂抹彩妆高危降级
    elif nom_risks or cofepris_risks:
        total_score = min(total_score * 0.65, 57.0)

    total_score = round(total_score, 1)

    # 评级标签与实战行动建议
    if total_score >= 80:
        tier = "S级·强烈推荐测款"
        verdict = f"[{data_tier_label}] 日均动销 {avg_daily_7d:.1f} 单 + 黄金客单价高毛利 + 免认证轻小件，建议立即 1688 核价并首批空运 100 件测款"
    elif total_score >= 70:
        tier = "A级·潜力候选品"
        if is_low_price_trap:
            verdict = f"[{data_tier_label}] 动销极快但单件售价(${price_mxn:.0f})偏低，必须在 1688 组合成【2~3件家庭装】提价至 $199+ MXN 方可盈利"
        else:
            verdict = f"[{data_tier_label}] 具备明显起量趋势且非红海垄断，建议点击「🔬 深潜详情页」穿透达人数据并对比 1688 差评微创新切入"
    elif total_score >= 56:
        tier = "B级·谨慎观察/需改造"
        if is_low_price_trap:
            verdict = f"⚠️ 单件售价 ${price_mxn:.0f} MXN 不够付 30 比索本土尾程费！切勿单件跟卖，仅可作为组合装赠品或 3 件套捆绑测款"
        elif nom_risks or cofepris_risks:
            verdict = "⚠️ 存在动销但涉及墨西哥 NOM 强电或 COFEPRIS 卫生监管，无认证新手切勿盲目海运囤货"
        else:
            verdict = "动销斜率一般或处于平稳期，建议先加入收藏观察跨日增量"
    else:
        tier = "C级·建议淘汰/避开"
        verdict = "大牌/IP侵权红线、严重强监管高危、或低价亏本通货，不符合墨西哥本土轻资产高毛利囤货策略"

    return {
        "potential_score": total_score,
        "tier": tier,
        "verdict": verdict,
        "data_tier": "FLAGSHIP" if is_flagship_data else "STANDARD",
        "data_tier_label": data_tier_label,
        "is_big_brand": 1 if is_big_brand else 0,
        "is_low_price_trap": 1 if is_low_price_trap else 0,
        "risk_level": risk_level,
        "compliance_tags": compliance_tags,
        "radar_scores": {
            "momentum": round(s_momentum, 1),
            "creator_health": round(s_creator, 1),
            "blue_ocean": round(s_blue_ocean, 1),
            "logistics_fit": round(s_logistics, 1),
            "price_band": round(s_price, 1),
        },
        "metrics_derived": {
            "avg_daily_7d": round(avg_daily_7d, 1),
            "avg_daily_28d": round(lifetime_daily, 1),
            "acceleration_ratio": round(acceleration_ratio, 2),
        },
    }
