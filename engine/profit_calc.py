# -*- coding: utf-8 -*-
"""
墨西哥 TikTok Shop 本土海外仓囤货双阶段毛利精算模型
阶段 1：空运小批快速测款 (Air Freight Test Batch)
阶段 2：海运大货放大补货 (Sea Freight Scale-Up)
"""

import re
import urllib.parse
from typing import Dict, Any, List


def calculate_mexico_profit(
    price_mxn: float,
    cost_1688_rmb: float,
    weight_g: float,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    输入墨西哥前台售价 (MXN)、1688 采购价 (RMB)、单件含包装重量 (g)，
    同屏测算空运测款与海运囤货的完整财务模型。
    """
    rate = float(params.get("exchange_rate_mxn_per_rmb", 2.80))
    air_kg_rmb = float(params.get("air_freight_rmb_per_kg", 75.0))
    sea_kg_rmb = float(params.get("sea_freight_rmb_per_kg", 20.0))
    platform_fee_rate = float(params.get("platform_fee_rate", 0.09))
    affiliate_rate = float(params.get("affiliate_commission_rate", 0.12))
    fulfillment_mxn = float(params.get("local_fulfillment_mxn", 30.0))
    buffer_rate = float(params.get("return_ad_buffer_rate", 0.05))
    test_qty = int(params.get("test_batch_qty", 100))

    price_mxn = max(float(price_mxn or 0), 1.0)
    cost_1688_rmb = max(float(cost_1688_rmb or 0), 0.1)
    weight_kg = max(float(weight_g or 250.0), 10.0) / 1000.0

    # 折算为人民币与比索
    revenue_rmb = price_mxn / rate
    fulfillment_rmb = fulfillment_mxn / rate

    # 平台与达人固定扣点 (按售价比例)
    platform_fee_mxn = price_mxn * platform_fee_rate
    affiliate_fee_mxn = price_mxn * affiliate_rate
    buffer_fee_mxn = price_mxn * buffer_rate

    platform_fee_rmb = platform_fee_mxn / rate
    affiliate_fee_rmb = affiliate_fee_mxn / rate
    buffer_fee_rmb = buffer_fee_mxn / rate

    # 头程运费 (RMB)
    air_Shipping_rmb = weight_kg * air_kg_rmb
    sea_Shipping_rmb = weight_kg * sea_kg_rmb

    # 阶段 1：空运测款模型
    air_total_cost_rmb = (
        cost_1688_rmb
        + air_Shipping_rmb
        + fulfillment_rmb
        + platform_fee_rmb
        + affiliate_fee_rmb
        + buffer_fee_rmb
    )
    air_profit_rmb = revenue_rmb - air_total_cost_rmb
    air_profit_mxn = air_profit_rmb * rate
    air_margin_pct = (air_profit_rmb / revenue_rmb) * 100.0 if revenue_rmb > 0 else 0.0

    # 100件空运测款首批压货总资金 (仅含拿货成本 + 空运头程)
    air_upfront_batch_rmb = (cost_1688_rmb + air_Shipping_rmb) * test_qty

    # 阶段 2：海运囤货放大模型
    sea_total_cost_rmb = (
        cost_1688_rmb
        + sea_Shipping_rmb
        + fulfillment_rmb
        + platform_fee_rmb
        + affiliate_fee_rmb
        + buffer_fee_rmb
    )
    sea_profit_rmb = revenue_rmb - sea_total_cost_rmb
    sea_profit_mxn = sea_profit_rmb * rate
    sea_margin_pct = (sea_profit_rmb / revenue_rmb) * 100.0 if revenue_rmb > 0 else 0.0

    # 500件海运备货压货资金
    sea_upfront_500_rmb = (cost_1688_rmb + sea_Shipping_rmb) * 500

    # 保本广告 ROI (Break-even ROAS = 1 / 扣除广告前的海运毛利率)
    margin_before_ad = (sea_profit_rmb + buffer_fee_rmb) / revenue_rmb if revenue_rmb > 0 else 0.01
    breakeven_roi = round(1.0 / max(margin_before_ad, 0.05), 2)

    # 中墨采销倍率 (售价折合RMB / 1688拿货价)
    markup_multiple = round(revenue_rmb / max(cost_1688_rmb, 0.5), 2)

    # 智能立项判定
    if sea_margin_pct >= 32.0 and air_margin_pct >= 8.0:
        decision = "🟢 强烈建议立项测款"
        decision_detail = (
            f"海运净利率达 {sea_margin_pct:.1f}%，且空运测款阶段即可实现单件盈利 "
            f"(+{air_profit_rmb:.1f}元/单)，{test_qty}件空运测款仅需启动资金 ¥{air_upfront_batch_rmb:,.0f}。"
        )
    elif sea_margin_pct >= 24.0:
        decision = "🟡 可立项(需控重量或提价)"
        decision_detail = (
            f"海运阶段有 {sea_margin_pct:.1f}% 利润空间，但空运测款阶段利润较薄 ({air_margin_pct:.1f}%)，"
            f"建议优先找 1688 源头厂压低拿货价 15% 或做组合装拉高客单价。"
        )
    else:
        decision = "🔴 利润过薄·不建议囤货"
        decision_detail = (
            f"扣除墨西哥海外仓尾程({fulfillment_mxn:.0f} MXN)与达人佣金后，海运净利率仅 {sea_margin_pct:.1f}%，"
            f"难以抗住退货与广告损耗，建议放弃或提价至 {round((sea_total_cost_rmb * 1.45) * rate, 0):.0f} MXN 以上。"
        )

    return {
        "price_mxn": round(price_mxn, 2),
        "revenue_rmb": round(revenue_rmb, 2),
        "cost_1688_rmb": round(cost_1688_rmb, 2),
        "weight_g": round(weight_g, 0),
        "markup_multiple": markup_multiple,
        "breakdown_rmb": {
            "cost_1688": round(cost_1688_rmb, 2),
            "air_shipping": round(air_Shipping_rmb, 2),
            "sea_shipping": round(sea_Shipping_rmb, 2),
            "local_fulfillment": round(fulfillment_rmb, 2),
            "platform_fee": round(platform_fee_rmb, 2),
            "affiliate_commission": round(affiliate_fee_rmb, 2),
            "return_ad_buffer": round(buffer_fee_rmb, 2),
        },
        "air_test_stage": {
            "total_cost_rmb": round(air_total_cost_rmb, 2),
            "net_profit_rmb": round(air_profit_rmb, 2),
            "net_profit_mxn": round(air_profit_mxn, 2),
            "margin_pct": round(air_margin_pct, 1),
            "batch_qty": test_qty,
            "upfront_capital_rmb": round(air_upfront_batch_rmb, 0),
        },
        "sea_scale_stage": {
            "total_cost_rmb": round(sea_total_cost_rmb, 2),
            "net_profit_rmb": round(sea_profit_rmb, 2),
            "net_profit_mxn": round(sea_profit_mxn, 2),
            "margin_pct": round(sea_margin_pct, 1),
            "batch_qty": 500,
            "upfront_capital_rmb": round(sea_upfront_500_rmb, 0),
            "breakeven_roi": breakeven_roi,
        },
        "decision": decision,
        "decision_detail": decision_detail,
    }


def build_1688_search_links(keywords_cn: List[str], image_url: str = "") -> Dict[str, Any]:
    """
    生成 1688 关键词源头工厂搜索直达链接与以图搜款辅助链接
    显式携带 _input_charset=utf-8&n=y，通知 1688 服务端按 UTF-8 精准解析中文，彻底防止搜索框回显乱码。
    """
    links = []
    for kw in (keywords_cn or []):
        if not kw or not str(kw).strip():
            continue
        kw_clean = str(kw).strip()
        # 清洗分类层级符号如 ">" 及常见前缀
        if ">" in kw_clean:
            kw_clean = kw_clean.split(">")[-1].strip()
        # 去除 Emoji 杂质
        kw_clean = re.sub(r"[\U00010000-\U0010ffff]|[\uD800-\uDBFF][\uDC00-\uDFFF]", "", kw_clean).strip()
        if not kw_clean:
            continue
        encoded_utf8 = urllib.parse.quote(kw_clean)
        links.append(
            {
                "keyword": kw_clean,
                "url": f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_utf8}&_input_charset=utf-8&n=y",
            }
        )
    return {
        "keyword_links": links,
        "image_search_portal": "https://www.1688.com/",
        "product_image_url": image_url,
    }
