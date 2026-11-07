# -*- coding: utf-8 -*-
"""
墨西哥 TikTok Shop 二级标准类目映射与表格多格式精准解析引擎
将 FastMoss 超过 180 个零散三级类目统一归口为 9 大标准一级赛道 + 保留精准三级细分类目
"""

import datetime
import re
from typing import Dict, Any, Tuple

# 9 大标准一级行业赛道定义与关键词规则
SECTOR_RULES = [
    (
        "💄 美妆个护与美甲",
        [
            "美妆", "个护", "口红", "唇", "睫毛", "化妆", "美甲", "指甲", "香水", "护肤", "面部",
            "眼影", "粉底", "定妆", "卸妆", "卷、直发", "发刷", "梳子", "头发", "头皮", "假发",
            "剃须", "脱毛", "口腔", "牙", "沐浴", "身体乳", "防晒", "纹身", "美容",
            "belleza", "maquillaje", "labial", "uñas", "cabello", "perfume", "facial",
        ],
    ),
    (
        "🏠 居家日用与厨卫收纳",
        [
            "居家", "日用", "厨房", "厨", "卫浴", "浴室", "收纳", "平底锅", "炒锅", "锅", "刀",
            "保温杯", "水杯", "杯", "餐具", "烘培", "家纺", "床单", "枕", "床垫", "地毯", "窗帘",
            "毛巾", "照明", "灯", "去污", "清洁", "垃圾", "洗衣", "衣架", "挂钩", "厕所用纸", "湿巾",
            "驱虫", "香薰", "装饰", "家具", "沙发", "桌", "椅",
            "hogar", "cocina", "baño", "organizador", "fregadero", "rallador", "bolsas",
        ],
    ),
    (
        "👗 女装与塑身内衣",
        [
            "女装", "女士", "连衣裙", "塑身", "文胸", "内衣", "内裤", "睡衣", "睡裙", "泳衣",
            "打底裤", "紧身裤", "牛仔裤", "半身裙", "女式", "吊带", "抹胸", "袜", "女鞋", "平底鞋",
            "高跟鞋", "女士靴", "女士拖鞋", "女士夹克", "女士卫衣", "女士短袖", "女士套装", "女士马甲",
            "mujer", "vestido", "faja", "reductor", "blusa", "chamarra", "lencería",
        ],
    ),
    (
        "👔 男装与箱包配饰",
        [
            "男装", "男士", "男鞋", "单肩包", "斜挎包", "背包", "双肩包", "钱包", "行李箱", "箱包",
            "太阳镜", "眼镜", "帽子", "皮带", "腰带", "围巾", "手套", "首饰", "项链", "耳环", "戒指",
            "手链", "手表", "发饰", "配饰",
            "hombre", "bolso", "mochila", "lentes", "gorra", "reloj", "joyería",
        ],
    ),
    (
        "📱 3C数码与手机配件",
        [
            "手机", "数码", "电脑", "办公", "充电", "移动电源", "充电宝", "数据线", "保护壳", "保护膜",
            "屏幕", "支架与底座", "平板", "耳机", "音响", "扬声器", "麦克风", "集线器", "读卡器", "键盘",
            "鼠标", "摄像头", "智能手表", "游戏机", "电视", "天线", "投影", "相机", "小家电", "吹风机",
            "风扇", "加湿器", "挂烫机",
            "electrónica", "auriculares", "cargador", "funda", "celular", "tv", "antena", "bluetooth",
        ],
    ),
    (
        "🚗 汽摩配件与五金工具",
        [
            "汽", "车", "摩托", "五金", "工具", "手动工具", "电动工具", "电钻", "扳手", "螺丝",
            "焊接", "测量", "园艺", "水管", "水枪", "喷壶", "胶带", "粘合", "锁", "安全防护",
            "auto", "coche", "carro", "moto", "herramienta", "soporte magnético", "espuma",
        ],
    ),
    (
        "🐾 宠物与玩具文教",
        [
            "宠物", "猫", "狗", "水族", "鸟", "玩具", "减压", "积木", "玩偶", "公仔", "桌游",
            "派对", "礼品袋", "节日", "书籍", "文具", "笔记本", "画", "笔", "教育", "学校",
            "母婴", "儿童", "婴儿", "奶瓶", "童装", "童鞋",
            "mascota", "perro", "gato", "juguete", "navideñ", "regalo", "niños", "bebé",
        ],
    ),
    (
        "🏃 运动户外与露营",
        [
            "运动", "户外", "健身", "瑜伽", "露营", "帐篷", "钓鱼", "骑行", "球", "护具",
            "泳", "登山", "望远镜", "手电筒",
            "deporte", "fitness", "camping", "yoga", "bicicleta",
        ],
    ),
    (
        "💊 保健与食品百货",
        [
            "保健", "维生素", "蛋白粉", "胶原蛋白", "减肥", "膳食", "食品", "零食", "糖果",
            "巧克力", "咖啡", "茶", "饮料", "泡面", "干粮", "调味", "医疗", "护理", "按摩", "体重秤",
            "suplemento", "vitamina", "colágeno", "salud", "comida",
        ],
    ),
]


def classify_category(raw_cat: str, title: str = "") -> Tuple[str, str]:
    """
    输入原始类目字符串和商品标题，返回 (一级标准赛道名称, 清洗后的三级细分类目名称)
    """
    sub_cat = str(raw_cat or "").strip()
    # 如果 sub_cat 是纯数字（之前列偏移导致的销量数字如 '4441'），则置空由标题或重新解析补齐
    if re.fullmatch(r"[\d,.\s]+", sub_cat) or sub_cat in ("", "墨西哥热销品类", "墨西哥热销"):
        sub_cat = ""

    # 若包含 '>'，取最后一级作为三级细分名
    if ">" in sub_cat:
        parts = [p.strip() for p in sub_cat.split(">") if p.strip()]
        leaf_cat = parts[-1] if parts else sub_cat
    else:
        leaf_cat = sub_cat

    combined_text = f"{sub_cat} {leaf_cat} {title}".lower()

    for main_sector, keywords in SECTOR_RULES:
        for kw in keywords:
            if kw.lower() in combined_text:
                clean_leaf = leaf_cat if leaf_cat else main_sector.split(" ")[-1]
                return main_sector, clean_leaf

    return "📦 综合日用百货", (leaf_cat if leaf_cat else "综合百货")


def parse_fastmoss_product_cell_lines(prod_cell_text: str) -> Dict[str, Any]:
    """
    精准解析 FastMoss 『商品』单元格的多行文本（兼容搜索页、飙升榜、新品榜所有格式）：
    格式示例 A (新品榜):
      Line 0: Chamarra BloZzom Con Gorro Desmontable Talla S M L y XL Manga Larga
      Line 1: 售价：MX$362.00
      Line 2: 上架时间：2026-11-01
    格式示例 B (搜索页 / 商品库):
      Line 0: Set de 12 Labiales Indelebles Mate Larga Duración Caja con 12 Piezas Set Nude
      Line 1: 售价：MX$117.00 (或 售价：MX$88.30 - 97.90)
      Line 2: 口红与唇彩
      Line 3: 4.5
      Line 4: 佣金比例：15% (或 佣金比例：-)
      Line 5: SKU库存
    """
    lines = [ln.strip() for ln in str(prod_cell_text or "").split("\n") if ln.strip()]
    title = lines[0] if lines else ""
    price_mxn = 0.0
    release_date = ""
    days_online = 15
    embedded_category = ""
    rating = 4.7
    commission_pct = 12.0

    for ln in lines[1:]:
        if "售价" in ln or "MX$" in ln or "$" in ln:
            # 若是区间价 MX$88.30 - 97.90，取第一个价格或均值
            nums = [float(x.replace(",", "")) for x in re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", ln)]
            if nums:
                price_mxn = nums[0]
        elif "上架时间" in ln or re.search(r"\d{4}-\d{2}-\d{2}", ln):
            dm = re.search(r"(\d{4}-\d{2}-\d{2})", ln)
            if dm:
                release_date = dm.group(1)
                try:
                    dt = datetime.datetime.strptime(release_date, "%Y-%m-%d").date()
                    days_online = max(1, min(365, (datetime.date.today() - dt).days))
                except Exception:
                    pass
        elif "佣金" in ln:
            nums = re.findall(r"\d+(?:\.\d+)?", ln)
            if nums:
                commission_pct = float(nums[0])
        elif re.fullmatch(r"\d\.\d", ln):
            rating = float(ln)
        elif ln not in ("SKU库存", "操作", "-") and not ln.isdigit():
            if not embedded_category:
                embedded_category = ln

    return {
        "title": title,
        "price_mxn": price_mxn,
        "release_date": release_date,
        "days_online": days_online,
        "embedded_category": embedded_category,
        "rating": rating,
        "commission_pct": commission_pct,
    }
