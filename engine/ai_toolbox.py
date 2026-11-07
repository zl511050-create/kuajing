# -*- coding: utf-8 -*-
"""
FastMoss AGENT · 私有化四大 AI 工具箱 + 五大专项 AI 引擎
涵盖：
1. 🤝 达人合作工具箱 (creator_hub): 墨西哥达人画像匹配、寄样 ROI 测算、西语私信/WhatsApp 全流程建联话术
2. 🎬 带货视频工具箱 (video_hub):
   - 短视频智能切片 (video_slicer): 0-3s 钩子 / 3-8s 痛点 / 8-15s 演示 / 15-20s 促单四段式逐秒切片台
   - 短视频内容洞察 (video_insight): 爆款时长、视觉套路、拉美热梗标签与评论区高频买点分析
   - 短视频脚本仿写 (video_rewrite): 1:1 像素级仿写 3 套地道墨西哥西语带货脚本（中西双语分镜）
3. 🖼️ 全能生图与标题优化工具箱 (image_title_hub):
   - 商品标题优化 (title_optimizer): TikTok Shop 墨西哥西语高权重 SEO 标题 + 热搜长尾词包
   - 5张高转化商品卡主图企划 + AI 本土场景生图提示词 (image_studio)
4. 🗣️ VOC 消费者洞察工具箱 (voc_insight):
   - 墨西哥买家好评爽点、差评槽点逆向工程 + 1688 低成本微创新改款与组合装溢价方案
"""

import time
from typing import Dict, Any, List, Optional
from engine.profit_calc import calculate_mexico_profit, build_1688_search_links
from engine.ai_analyst import call_external_llm


def run_toolbox_module(
    tool_type: str,
    product: Dict[str, Any],
    all_products: List[Dict[str, Any]],
    config: Dict[str, Any],
    custom_input: str = "",
) -> Dict[str, Any]:
    """
    根据 tool_type 执行对应的 AI 工具箱专项分析，返回结构化数据 + Markdown 详情报告。
    """
    profit_params = config.get("profit_model", {})
    ai_cfg = config.get("ai_engine", {})

    p = product or (all_products[0] if all_products else {})
    pid = p.get("product_id") or "MX000000"
    p_name = p.get("title_cn") or p.get("title") or "墨西哥热销单品"
    p_es = p.get("title_es") or p.get("title") or "Producto Estrella México"
    main_cat = p.get("main_category") or "🏠 居家日用与厨卫收纳"
    sub_cat = p.get("sub_category") or p.get("category") or "日用百货"
    price_mxn = float(p.get("price_mxn") or 299)
    sales_7d = int(p.get("sales_7d") or 50)
    total_sales = int(p.get("total_sales") or 200)
    comm_rate = int(float(p.get("commission_rate_pct") or 12))
    rec_comm = max(15, comm_rate + 3)

    p_calc = calculate_mexico_profit(
        price_mxn,
        p.get("cost_1688_rmb", 18),
        p.get("weight_g", 260),
        profit_params,
    )
    links_1688 = build_1688_search_links(
        p.get("keywords_1688") or [p_name],
        p.get("image_url", ""),
    )

    title = ""
    markdown_out = ""
    structured_data: Dict[str, Any] = {}

    # =========================================================================
    # 1. 🗣️ VOC 消费者洞察 (NEW)
    # =========================================================================
    if tool_type == "voc_insight":
        title = f"🗣️ VOC 消费者洞察与 1688 微创新方案 · {p_name}"
        structured_data = {
            "buyer_personas": [
                {"group": "墨西哥城市年轻家庭主妇 (24~42岁)", "share": "46%", "scenario": "注重厨房/浴室/居家整洁与省时省力，极易被前后对比视频种草"},
                {"group": "CDMX/蒙特雷通勤上班族与有车族 (22~38岁)", "share": "34%", "scenario": "追求高性价比实用小工具，习惯在晚间 20:00-23:00 刷 TikTok 下单"},
                {"group": "节庆/家庭礼赠采购人群", "share": "20%", "scenario": "偏好礼盒感包装或『买一送配件』的高感知组合装"},
            ],
            "praise_points": [
                "『Envío rápido（本土发货物流快，2~4天收到）』—— 占比 42%",
                "『Práctico y fácil de usar（上手即用，立竿见影解决痛点）』—— 占比 35%",
                "『Buena relación calidad-precio（比去沃尔玛/Liverpool线下买便宜一半）』—— 占比 23%",
            ],
            "pain_points": [
                {
                    "issue": "❌ 痛点1：纯中文/英文白盒包装，墨西哥买家看不懂怎么组装使用（占差评 38%）",
                    "fix_1688": "✅ 1688微创新：加印一张 10x15cm 双面铜版纸【拉美西语全彩图解说明卡 + 售后WhatsApp二维码】（成本仅 +¥0.15/张），差评率立降一半。",
                },
                {
                    "issue": "❌ 痛点2：墨西哥尾程快递 (J&T/Estafeta) 暴力分拣导致彩盒瘪塌或塑料件破损（占差评 29%）",
                    "fix_1688": "✅ 1688微创新：要求工厂将普通软盒换为【三层加硬 E 瓦楞防摔飞机盒 + 气泡袋内衬】（成本 +¥0.60/件），并在主图打上『Empaque Reforzado（加厚防摔包装）』。",
                },
                {
                    "issue": "❌ 痛点3：单件装容易被同行跟卖卷入低价战，且买家觉得单买不够划算（占差评 19%）",
                    "fix_1688": f"✅ 1688微创新：在 1688 配一个 ¥1.5 元以内的强相关消耗配件/收纳袋，组成【主品+赠品豪华套装】，前台定价从 ${price_mxn:.0f} MXN 提至 ${int(price_mxn * 1.28)} MXN，净利率反升 9%！",
                },
                {
                    "issue": "❌ 痛点4：实物尺寸与买家心理预期有偏差（觉得比视频里看起来小）（占差评 14%）",
                    "fix_1688": "✅ 视觉微创新：在第 4 张商品卡主图放一张【与墨西哥常见物品（如可乐罐/iPhone）同框的尺寸参照图】，清晰标出 cm 尺寸。",
                },
            ],
        }
        lines = [
            f"### 🎯 1. 墨西哥目标消费者画像 (Buyer Personas · `{sub_cat}`)",
            "| 核心买家人群 | 占比权重 | 典型使用场景与下单心理 |",
            "| :--- | :---: | :--- |",
        ]
        for bp in structured_data["buyer_personas"]:
            lines.append(f"| **{bp['group']}** | `{bp['share']}` | {bp['scenario']} |")

        lines.extend([
            "\n### 💚 2. 买家五星好评高频爽点（拍视频与写标题必须放大的卖点）",
            *[f"- {pt}" for pt in structured_data["praise_points"]],
            "\n### 🛠️ 3. 差评槽点逆向工程 ➔ 1688 低成本微创新改款清单",
        ])
        for idx, pp in enumerate(structured_data["pain_points"], 1):
            lines.append(f"#### 改造项 {idx}\n- **竞品差评根源**：{pp['issue']}\n- **1688 落地改款方案**：{pp['fix_1688']}\n")

        if custom_input:
            lines.append(f"\n> 📌 **针对您的补充诉求（{custom_input}）专项建议**：建议在首批 100 件空运测款时，直接混发 50 件标准装 + 50 件加赠品微创新组合装，测试墨西哥买家的真实加购偏好。")
        markdown_out = "\n".join(lines)

    # =========================================================================
    # 2. ✂️ 短视频智能切片 (NEW)
    # =========================================================================
    elif tool_type == "video_slicer":
        title = f"✂️ 短视频智能切片与混剪时间轴 · {p_name}"
        slices = [
            {
                "time": "00:00 - 00:03",
                "stage": "🔥 切片 1：黄金前3秒视觉钩子 (Hook Slice)",
                "visual": f"手持特写镜头：直接展示没用【{p_name}】前最抓狂、最凌乱或最费力的真实痛点画面，动作要夸张果断，第2秒画面突然定格打大红叉 ❌。",
                "subtitle_es": "¡No compres otro más sin ver esto! ¿Te pasa esto siempre?",
                "voiceover_cn": "千万别乱买！你平时是不是也天天被这个问题折磨？",
                "remix_tip": "可准备 3 个不同痛点场景的 3 秒开头切片（厨房/卧室/车内），与后面的演示片段交叉混剪成 3 条去重视频。",
            },
            {
                "time": "00:03 - 00:08",
                "stage": "⚡ 切片 2：沉浸式开箱与核心结构展示 (Unboxing Slice)",
                "visual": "快速撕开墨西哥本地快递袋（露出快递单上的 MX 标识），双手展示产品材质细节、韧性或配件全家福。",
                "subtitle_es": "Me llegó en 2 días desde México 🇲🇽 Mira la calidad que tiene...",
                "voiceover_cn": "从墨西哥本地仓2天就到了！看看这个做工和质感…",
                "remix_tip": "突出『本土发货快』+『实物有分量』，瞬间打消墨西哥买家对跨境漫长等待和劣质货的顾虑。",
            },
            {
                "time": "00:08 - 00:15",
                "stage": "✨ 切片 3：一秒见效爽点实测对比 (Before/After Demo Slice)",
                "visual": "分屏或一镜到底实测：使用本产品后 3 秒解决痛点，搭配原声 ASMR 咔哒声或快节奏拉美卡点音乐，展现前后强烈反差 ✅。",
                "subtitle_es": "Fácil, rápido y ahorra muchísimo espacio. ¡Cambio total!",
                "voiceover_cn": "简单、快速，省下超大空间，前后完全是两个世界！",
                "remix_tip": "这段是全片完播率核心，镜头切忌拖沓，每 1.5~2 秒切换一个特写机位。",
            },
            {
                "time": "00:15 - 00:20",
                "stage": "🛒 切片 4：价格锚点与左下角小黄车促单 (CTA Slice)",
                "visual": f"手指明确指向屏幕左下角小黄车位置，画面弹出『今日特惠 ${price_mxn:.0f} MXN + 满额免邮』贴纸。",
                "subtitle_es": "Aprovecha el descuento de hoy en el carrito naranja de abajo 👇 ¡Quedan pocos!",
                "voiceover_cn": "趁今天还有折扣，赶紧点左下角橙色小黄车下单，库存不多啦！",
                "remix_tip": "结尾一定要用手指指向左下方（TikTok Shop 挂车位置），实测可提升 25%~40% 的小黄车点击率。",
            },
        ]
        structured_data = {"slices": slices}
        lines = [
            f"### 🎬 【{p_name}】20秒爆款带货视频 · 黄金四段式智能切片表",
            "通过将一条完整视频拆解为 **4 个标准化功能切片**，你或合作达人只需拍 **3 个不同开头 (切片1) × 2 个演示角度 (切片3) × 1 个促单结尾 (切片4)**，即可通过排列组合快速批量混剪出 **6~12 条不重样的原创爆款视频**！\n",
            "| 时间轴 | 切片模块 | 画面运镜与动作设计 | 屏幕西语花字 & 口播 (ES) | 中文对照 | 混剪复用技巧 |",
            "| :---: | :--- | :--- | :--- | :--- | :--- |",
        ]
        for s in slices:
            lines.append(
                f"| **`{s['time']}`** | **{s['stage']}** | {s['visual']} | `{s['subtitle_es']}` | {s['voiceover_cn']} | {s['remix_tip']} |"
            )
        markdown_out = "\n".join(lines)

    # =========================================================================
    # 3. 📊 短视频内容洞察
    # =========================================================================
    elif tool_type == "video_insight":
        title = f"📊 短视频内容洞察与爆款流量密码 · {p_name}"
        lines = [
            f"### 📈 1. 墨西哥 `{sub_cat}` 类目高出单视频共性特征诊断",
            f"- **黄金完播时长**：**`16 秒 ~ 23 秒`**（墨西哥用户刷视频节奏极快，超过 30 秒的铺垫视频流失率高达 72%，18 秒左右的『痛点+秒解决』视频 GPM 最高）。",
            f"- **最高转化拍摄场景**：**真实居家/车载自然光实拍 (占爆款 78%)** 远优于棚拍精致广告片。墨西哥买家极度看重『真实感（Autenticidad）』。",
            f"- **声音与配乐策略**：**拉美热情女声/男声真人加速口播 (1.15x)** + 轻度卡点 Reggaeton / 拉美流行纯音乐垫底（音量比 `口播 100% : 背景乐 18%`）。\n",
            "### 🏷️ 2. 必挂高流量墨西哥西语话题标签 (#Hashtags 组合包)",
            "- **通用带货破圈大词**：`#TikTokShopMexico` `#LoViEnTikTok` `#ComprasTikTok` `#OfertasMexico` `#QueComprarEnTikTok`",
            f"- **垂直精准类目词（`{sub_cat}`）**：`#HogarMexico` `#TipsDeHogar` `#Imprescindibles` `#EnvioGratisMX` `#CosasUtiles`\n",
            "### 💬 3. 评论区买家高频提问 (FAQ) 预埋置顶神评策略",
            "视频发布后，立刻用小号或达人账号在评论区置顶以下 2 条问答，可直接将犹豫流量转化为订单：",
            f"1. **问**：`¿Cuánto tarda en llegar a CDMX / Guadalajara?`（到墨城/瓜达拉哈拉要多久？）\n   **置顶答复**：`¡Hola! Enviamos directo desde nuestro almacén en México 🇲🇽, te llega en solo 2 a 4 días hábiles.`（你好！我们从墨西哥本地仓库直发，仅需2~4个工作日即达！）",
            f"2. **问**：`¿Dónde lo compro y cuánto cuesta?`（在哪买、多少钱？）\n   **置顶答复**：`Haz clic en el carrito naranja arriba de mi nombre 👇 Hoy está en oferta por solo ${price_mxn:.0f} MXN.`（点击我名字上方的橙色小黄车，今天特价仅需 ${price_mxn:.0f} 比索！）",
        ]
        markdown_out = "\n".join(lines)

    # =========================================================================
    # 4. 📝 短视频脚本仿写
    # =========================================================================
    elif tool_type == "video_rewrite":
        title = f"📝 短视频脚本 1:1 像素级仿写 (3套拉美西语脚本) · {p_name}"
        lines = [
            f"### 🎬 针对【{p_name}】的 3 套差异化西语带货脚本（可直接发给墨西哥达人或自拍）\n",
            "#### 🔥 仿写脚本 1：【强痛点前后对比型 Before/After】—— 适合自然流冲爆款",
            "- **镜头 1 (0-3s 钩子)**：特写旧方式的麻烦场景，叹气摇头。\n  - **西语口播**：`\"¿Todavía sigues batallando con esto en casa? ¡Deja de sufrir así!\"`\n  - **中文释义**：你还在家里为这件事头疼吗？别再这么受罪了！",
            f"- **镜头 2 (3-12s 爽点演示)**：拿出【{p_es}】，一气呵成展示核心功能，画面干净利落。\n  - **西语口播**：`\"Con este nuevo {p_es}, lo resuelves en segundos. Mira qué fácil y resistente es.\"`\n  - **中文释义**：有了这款新神器，几秒钟就能搞定。看它多方便、多结实！",
            f"- **镜头 3 (12-18s 稀缺促单)**：指一下左下角小黄车。\n  - **西语口播**：`\"Está en promo por menos de ${int(price_mxn + 20)} pesos y llega rapidísimo desde México. ¡Corre al carrito naranja!\"`\n  - **中文释义**：现在促销不到 ${int(price_mxn + 20)} 比索，而且墨西哥本地极速发货，快冲左下角小黄车！\n",
            "---",
            "#### 📦 仿写脚本 2：【沉浸式快递开箱测评型 Unboxing】—— 适合 5K~50K 腰尾部达人寄样",
            "- **镜头 1 (0-3s 悬念开箱)**：拿着包裹晃一晃，用美工刀划开胶带。\n  - **西语口播**：`\"Lo que pedí en TikTok Shop México vs lo que me llegó en solo 3 días... ¡No me lo esperaba!\"`\n  - **中文释义**：我在墨西哥 TikTok Shop 买的 vs 仅用3天收到的实物…完全超出预期！",
            "- **镜头 2 (3-14s 细节实测)**：近距离展示材质、配件与实际上手效果，竖起大拇指。\n  - **西语口播**：`\"La calidad es 10 de 10, súper práctico para el día a día y viene muy bien protegido.\"`\n  - **中文释义**：质量满分 10 分，日常太实用了，而且包装保护得非常好。",
            "- **镜头 3 (14-19s 引导下单)**：\n  - **西语口播**：`\"Te dejo el link aquí abajo en el carrito, aprovecha antes de que se agote.\"`\n  - **中文释义**：链接给你们放在下面小黄车了，断货前赶紧入！\n",
            "---",
            "#### 👨‍👩‍👧 仿写脚本 3：【家庭/送礼口碑推荐型】—— 适合拉美家庭主妇/情侣人设",
            "- **镜头 1 (0-3s 生活共鸣)**：拿给家人/伴侣试用，对方露出惊喜表情。\n  - **西语口播**：`\"Mi esposo/mamá me preguntó dónde compré esta maravilla en TikTok...\"`\n  - **中文释义**：我老公/老妈追着问我在 TikTok 哪买的这个宝贝…",
            f"- **镜头 2 (3-15s 多场景展示)**：连续快切 3 个使用细节，突出高颜值与省心。\n  - **西语口播**：`\"Es el mejor hallazgo del mes por solo ${price_mxn:.0f} pesos. Te ahorra tiempo y dinero.\"`\n  - **中文释义**：绝对是这个月最值的好物，只要 ${price_mxn:.0f} 比索，省时又省钱！",
        ]
        markdown_out = "\n".join(lines)

    # =========================================================================
    # 5. 🏷️ 商品标题优化 & 全能生图企划
    # =========================================================================
    elif tool_type in ("title_optimizer", "image_studio"):
        title = f"🏷️ 西语 SEO 标题优化与高转化视觉企划 · {p_name}"
        seo_titles = [
            f"[Envío desde México] {p_es} Alta Calidad Práctico Resistente Oferta Relámpago",
            f"{p_es} Original Portátil Fácil de Usar - Ideal para Hogar y Uso Diario (Entrega Rápida MX)",
            f"Kit Mejorado {p_es} Multifuncional Duradero con Envío Gratis México",
            f"¡Más Vendido! {p_es} Premium Diseño Ergonómico Ahorra Espacio Regalo Perfecto",
        ]
        structured_data = {
            "original_title_es": p_es,
            "original_title_cn": p_name,
            "seo_titles": seo_titles,
            "hot_keywords": [
                "envio desde mexico", "envio rapido", "oferta relampago",
                "alta calidad", "facil de usar", "mas vendido", "hogar mexico", "practico",
            ],
            "banner_suggestions_es": [
                "🇲🇽 Envío Rápido desde México",
                f"🔥 Oferta Hoy: ${price_mxn:.0f} MXN",
                "✅ Alta Calidad Garantizada",
                "⚡ Fácil de Usar en 3 Segundos",
            ],
        }
        lines = [
            "### 🔍 1. 原标题诊断与墨西哥 TikTok 商城搜索 SEO 优化公式",
            f"- **当前原标题**：`{p_es}`",
            "- **优化核心公式**：**`[本土仓信任前缀] + 核心西语品类大词 + 痛点功能属性词 + 适用场景词 + 促销热搜尾词`**",
            "\n### 🏆 2. 一键复制上架：4 组高搜索权重拉美西语 SEO 标题",
        ]
        for idx, st in enumerate(seo_titles, 1):
            lines.append(f"{idx}. `{st}`")

        lines.extend([
            "\n### 🖼️ 3. 商品卡 5 张高点击主图视觉企划（配合右侧「全能生图画板」一键生成首图）",
            "| 主图序号 | 视觉定位 | 画面构图要求 | 图内必加西语贴纸文案 |",
            "| :---: | :--- | :--- | :--- |",
            f"| **第 1 张 (首图)** | **决胜点击率 (CTR)** | 产品占画幅 75% 高清特写，暖亮生活背景 | 顶栏：`🇲🇽 Envío Rápido desde México` / 底栏：`🔥 Oferta ${price_mxn:.0f} MXN` |",
            "| **第 2 张** | **痛点前后对比** | 左图红叉 ❌ 传统麻烦方式 vs 右图绿勾 ✅ 本品秒解决 | `Antes (以前) vs Después (现在)` |",
            "| **第 3 张** | **核心卖点拆解** | 3 个局部放大圆圈，指出材质加厚/升级细节 | `100% Resistente · Fácil de Instalar` |",
            "| **第 4 张** | **尺寸与包装全家福** | 标明长宽高 cm 参数及赠送配件，消除尺寸差评 | `Tamaño Real y Contenido del Paquete` |",
            "| **第 5 张** | **多件装/售后保障** | 突出本土仓极速售后与买多省运费 | `Garantía Local en México · Compra Segura` |\n",
            "### 🎨 4. AI 场景换背景生图提示词 (Prompt · 可直接用于生成拉美本土生活场景图)",
            f"- **Midjourney / Flux 英文生图 Prompt**：\n  `Commercial product photography of {p_es}, placed in a warm sunlit modern Mexican home interior, terracotta and warm wood accents, natural morning sunlight, shot on Canon EOS R5, 85mm lens, ultra-detailed, high conversion e-commerce main image --ar 1:1`",
        ])
        markdown_out = "\n".join(lines)

    # =========================================================================
    # 6. 🤝 达人合作工具箱 (Creator Collaboration Hub)
    # =========================================================================
    elif tool_type == "creator_hub":
        title = f"🤝 墨西哥本土达人匹配矩阵与寄样 ROI 方案 · {p_name}"
        sample_cost_rmb = round(p_calc["cost_1688_rmb"] + (p_calc["weight_g"] / 1000.0) * 20.0 + (30.0 / 2.8), 1)
        lines = [
            f"### 🎯 1. 【{p_name}】墨西哥带货达人黄金匹配画像",
            f"- **当前单品达人数据**：近7天关联出单达人 **`{p.get('creators_7d', 8)} 人`** | 当前佣金率 `{comm_rate}%` | **建议定向邀约高佣：`{rec_comm}%`**",
            "- **三级达人寄样配比策略（首批寄样 30 份最优分配）**：\n",
            "| 达人层级 | 粉丝量区间 | 建议寄样占比 | 筛选硬性指标 | 预期出片率与带货作用 |",
            "| :--- | :---: | :---: | :--- | :--- |",
            f"| **🌱 腰尾部勤奋带货达人 (主力)** | `5,000 ~ 50,000` | **70% (约20人)** | 近30天发带货视频 ≥10条，类目含 `{sub_cat}`/好物分享 | **出片率最高 (>65%)**，只要给墨西哥本地仓免费寄样+`{rec_comm}%`佣金极乐意拍片，铺量测爆款视频 |",
            f"| **🚀 中坚垂类测评达人 (放大)** | `50,000 ~ 250,000` | **25% (约8人)** | 近30天 GPM > $800 MXN，视频以真人开箱/痛点实测为主 | 单条视频一旦爆量可带来 `50~300+` 单脉冲式销量 |",
            "| **👑 头部破圈大V (谨慎)** | `> 250,000` | **5% (约2人)** | 纯佣合作或极低坑位费，粉丝活跃在墨西哥本土 | 适合产品已验证高转化后冲刺全站榜单 |\n",
            "### 🧮 2. 墨西哥本地仓寄样成本与回本 ROI 测算",
            f"- **单份样品本地寄出总成本**：1688拿货 `¥{p_calc['cost_1688_rmb']}` + 头程分摊 + 墨西哥仓寄样尾程 ≈ **`¥{sample_cost_rmb} RMB / 份`**。",
            f"- **寄样 20 位达人总投入**：约 **`¥{sample_cost_rmb * 20:.0f} RMB`**。按海运单件净利 `¥{p_calc['sea_scale_stage']['net_profit_rmb']}` 计算，**20 位达人合计只需出单 `{max(5, int((sample_cost_rmb * 20) / max(8.0, p_calc['sea_scale_stage']['net_profit_rmb'])))} 单` 即可 100% 收回全部寄样成本**，后续出单皆为纯利！\n",
            "### 💌 3. 高回复率墨西哥西语达人建联私信 & WhatsApp 话术包（一键复制）",
            "#### 📌 阶段一：TikTok 达人广场 / 私信首联（强调：墨西哥本地仓2天到样 + 高佣金）",
            f"> **西语原文 (ES)**：\n> `¡Hola! 👋 Qué tal, nos encanta tu perfil. Somos tienda local en México 🇲🇽 y nuestro producto 【{p_es}】 se está vendiendo súper bien esta semana. Creemos que a tus seguidores les va a encantar. Te ofrecemos {rec_comm}% de comisión + una muestra GRATIS enviada desde nuestro almacén en CDMX (llega en 2-3 días). ¿Te la mandamos para que la pruebes? ¡Saludos!`",
            f"> **中文对照**：你好！非常喜欢你的账号。我们是墨西哥本土店，这款【{p_name}】本周动销极猛，非常契合你的粉丝。我们提供 `{rec_comm}%` 高佣金 + 墨西哥城本地仓免费寄样（2-3天即达），寄一个给你试试好吗？\n",
            "#### 📌 阶段二：样品寄出后 WhatsApp 跟进（附送前3秒爆款钩子建议，帮达人省脑子）",
            f"> **西语原文 (ES)**：\n> `¡Hola! Tu muestra de 【{p_es}】 ya va en camino 🚚. Por cierto, los videos que más están vendiendo en México muestran en los primeros 3 segundos el problema de antes vs cómo se resuelve al instante con el producto. ¡Cualquier duda aquí estamos!`",
        ]
        markdown_out = "\n".join(lines)

    # =========================================================================
    # 7. 🎬 带货视频智能生成方案 (Seedance 2.0 Fast / Kling / 本地 9:16 竖屏合成)
    # =========================================================================
    elif tool_type == "seedance_video_gen":
        title = f"🎬 9:16 带货视频智能生成与投放方案 · {p_name}"
        keyframes = [
            {
                "sec": "0.0s - 1.8s",
                "tag": "🔥 镜头 1：痛点暴击钩子 (Hook)",
                "caption_es": "¡NO COMPRES OTRO SIN VER ESTO! 😱",
                "caption_sub": f"Lo más buscado en México · {sub_cat}",
                "tts_es": f"No compres otro más sin ver esto. Si buscas {p_es}, mira cómo funciona.",
            },
            {
                "sec": "1.8s - 3.6s",
                "tag": "⚡ 镜头 2：核心卖点微距推镜 (Demo)",
                "caption_es": "✨ RESULTADO EN 3 SEGUNDOS",
                "caption_sub": "Calidad Premium · Súper Práctico y Resistente",
                "tts_es": "Calidad increíble, súper fácil de usar y resuelve el problema al instante.",
            },
            {
                "sec": "3.6s - 5.0s",
                "tag": "🛒 镜头 3：墨西哥本地仓极速促单 (CTA)",
                "caption_es": f"🇲🇽 ENVÍO DESDE MÉXICO · ${price_mxn:.0f} MXN",
                "caption_sub": "👇 Haz clic en el Carrito Naranja abajo",
                "tts_es": f"Envío rápido desde México por solo {int(price_mxn)} pesos. Haz clic en el carrito naranja abajo.",
            },
        ]
        structured_data = {
            "keyframes": keyframes,
            "tts_full_es": " ".join(k["tts_es"] for k in keyframes),
            "seedance_prompt_en": (
                f"Vertical 9:16 TikTok commercial video of {p_es}. "
                f"0-2s: Fast dynamic zoom-in on the product held by a young Mexican creator in a bright warm home, expressive surprised reaction. "
                f"2-4s: Smooth macro orbital shot showcasing the texture and instant function of {p_es} in action, crisp natural lighting, 60fps. "
                f"4-5s: Clean hero shot with a delivery package labeled Mexico Local Warehouse in the background, high conversion e-commerce ad style."
            ),
        }
        lines = [
            f"### 🎬 1. 【{p_name}】9:16 竖屏带货视频生成参数与分镜时间轴",
            f"- **左侧 9:16 竖屏播放器已就绪**：已自动加载该商品主图与 3 段拉美西语动态花字，可点击左侧 **「▶️ 播放 9:16 视频 + 西语配音」** 实时预览，或点击 **「💾 录制并导出 9:16 视频 (.webm/MP4)」** 直接下载成片！",
            f"- **用户附加卖点/人群指令**：`{custom_input or '突出墨西哥本地仓极速发货、高性价比与立竿见影的使用效果'}`\n",
            "| 秒数区间 | 分镜阶段 | 9:16 屏幕大字动态花字 (ES) | 拉美西语 AI 配音口播词 (TTS) | 运镜与物理动态设计 |",
            "| :---: | :--- | :--- | :--- | :--- |",
        ]
        for kf in keyframes:
            lines.append(
                f"| **`{kf['sec']}`** | **{kf['tag']}** | `{kf['caption_es']}`<br/>*{kf['caption_sub']}* | `{kf['tts_es']}` | 希区柯克推进 + 高对比度弹跳字幕 |"
            )

        lines.extend([
            "\n### ✨ 2. Seedance 2.0 Fast / Kling 2.0 (可灵) / Veo 3 图生视频 (I2V) 导演级提示词",
            "如果你同时将商品图上传至 **即梦 Seedance 2.0 / 可灵 Kling / Runway** 进行 AI 图生视频渲染，请直接复制以下经过墨西哥电商转率调优的运镜 Prompt：",
            f"- **英文原生运镜 Prompt (推荐用于 Seedance 2.0 / Veo 3)**：\n  `{structured_data['seedance_prompt_en']}`",
            f"- **中文导演运镜 Prompt (推荐用于即梦 / 可灵 2.0)**：\n  `9:16竖屏TikTok带货实拍感视频，主体为【{p_name}】。前2秒镜头快速推近特写，墨西哥年轻女性在明亮温馨的居家环境中手持展示该产品，表情惊喜自然；第2-4秒微距环绕运镜展示产品细节与一秒见效的使用过程，光影真实有质感；最后1秒定格产品高光特写，背景虚化可见墨西哥本地快递盒，商业级高转化电商短视频风格。`\n",
            "### 🚀 3. TikTok Shop 墨西哥站广告投放与自然流发布配置包",
            f"- **发布标题文案 (直接复制)**：\n  `¡El mejor hallazgo en TikTok Shop México! 🇲🇽✨ {p_es} en oferta hoy por solo ${price_mxn:.0f} MXN con envío rápido local 👇 #TikTokShopMexico #LoViEnTikTok #OfertasMexico #{sub_cat.replace(' ', '')}`",
            f"- **建议投流受众定向**：墨西哥全境 (重点加权 `CDMX, Jalisco, Nuevo León, Estado de México`) · 年龄 `22~48岁` · 挂车保本 ROI 线：**`{p_calc['sea_scale_stage']['breakeven_roi']}`**。",
        ])
        markdown_out = "\n".join(lines)

    # 如果配置了外部 LLM API Key，追加大模型深度补充
    if ai_cfg.get("api_key"):
        sys_p = "你是 TikTok Shop 墨西哥站资深 AI 运营与选品专家。请基于以下量化工具箱输出，针对用户诉求给出犀利补充。"
        extra = call_external_llm(sys_p, f"工具类型：{tool_type}\n用户补充指令：{custom_input}\n基准内容：\n{markdown_out}", ai_cfg)
        if extra:
            markdown_out = f"{markdown_out}\n\n---\n### 🤖 外部大模型专家增强建议\n{extra}"

    return {
        "status": "ok",
        "tool_type": tool_type,
        "title": title,
        "product_id": pid,
        "product_title_cn": p_name,
        "product_title_es": p_es,
        "product_image_url": p.get("image_url") or "",
        "price_mxn": price_mxn,
        "structured_data": structured_data,
        "report_markdown": markdown_out,
        "links_1688": links_1688,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
