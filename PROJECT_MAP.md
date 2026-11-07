# 项目核心架构与函数速查索引 (PROJECT_MAP)

本项目为 **FastMoss 墨西哥 TikTok 本土选品与智能体研判中枢**。本文件提供极简模块与核心函数速查索引，禁止展开代码实现。

---

## 一、 核心业务文件职责速查表

| 业务分类 | 文件路径 | 职责管辖 |
| :--- | :--- | :--- |
| **前端UI** | `static/index.html` | 单页 (SPA) 结构：选品大盘、排程看板、AI 研判台、利润测算器、主图/视频工作台及弹窗交互结构 |
| **前端UI** | `static/styles.css` | 科技暗色主题设计、响应式网格/表格布局、动态骨架屏及风险指示标签样式 |
| **交互逻辑** | `static/app.js` | 全局状态中枢 (`STATE`)、视图切换、异步调度、数据检索过滤、Canvas 渲染与视频流录制导出 |
| **交互逻辑** | `scraper/tampermonkey_bridge.user.js` | 油猴实时伴随脚本：在浏览器拦截 FastMoss 原始数据流并异步转发中枢入库 |
| **后端API** | `server.py` | 本地原生 HTTP 服务引擎 (端口 8688)：RESTful 路由分发、爬虫子进程唤醒与配置热重载 |
| **后端API** | `config.json` | 系统全局配置：选品门槛、大牌黑名单、墨西哥 3PL 利润模型参数与爬虫控制台规则 |
| **爬虫引擎** | `scraper/fm_collector.py` | Playwright + 本机 Chrome 驱动：多榜单自动巡航、详情页静默深潜、断点续抓与防风控拟人调度 |
| **爬虫引擎** | `scraper/live_status.json` | 爬虫引擎运行状态持久化心跳文件（供前端高频轮询任务进度） |
| **数据库** | `database/db_manager.py` | SQLite 访问层：表结构维护、商品 upsert 去重、五维蓝海评分持久化、看板与任务日志管理 |
| **数据库** | `database/fastmoss_hub.db` | 主业务 SQLite 数据库文件（包含 `products`, `scrape_tasks`, `agent_reports` 数据表） |
| **算法引擎** | `engine/scorer.py` | 选品量化评分算法：80+大牌与IP黑名单过滤、NOM/COFEPRIS合规风控熔断、五维潜力评分双模核算 |
| **算法引擎** | `engine/profit_calc.py` | 墨西哥 TikTok 全成本利润测算模型（头程空运、本土3PL尾程、平台扣点）与 1688 寻源链构建 |
| **算法引擎** | `engine/ai_analyst.py` | 选品研判工作流报告生成引擎，自动将 Markdown 报告持久化写入 `./exports/` 目录 |
| **算法引擎** | `engine/ai_toolbox.py` | 垂直 AI 工具箱引擎：VOC 差评痛点洞察、西语爆款脚本生成、1688 源头厂压价谈判话术 |
| **算法引擎** | `engine/taxonomy.py` | FastMoss DOM 单元格结构解析与商品类目规范化映射清洗 |
| **算法引擎** | `engine/es_translator.py` | 西班牙语标题分词翻译、多件套拆解、类目默认参数预估与 1688 检索词提取 |

---

## 二、 主要交互功能与函数映射速查表

| 核心交互功能 | 前端触发函数 (`static/app.js`) | 后端 API 路由 (`server.py`) | 底层执行核心函数 |
| :--- | :--- | :--- | :--- |
| **自动化巡航抓取** | `triggerPlaywright(mode)`<br>`resumePlaywrightScrape()`<br>`applyScraperSettings()` | `POST /api/scraper/trigger`<br>`POST /api/scraper/settings` | `scraper/fm_collector.py` -> `run_playwright_collector()`<br>`scraper/fm_collector.py` -> `goto_list_page()`<br>`scraper/fm_collector.py` -> `extract_products_from_dom()` |
| **巡航断点与安全停止** | `stopPlaywrightScrape()`<br>`discardCheckpoint()` | `POST /api/scraper/stop`<br>`POST /api/scraper/checkpoint/clear` | `scraper/fm_collector.py` -> `save_checkpoint()` / `load_checkpoint()`<br>`scraper/fm_collector.py` -> `check_stop_signal()` |
| **详情页靶向深潜**<br>*(单品 / 多选 / 筛选池批量)* | `triggerSingleDeepDive(pid)`<br>`triggerSelectedDeepDive()`<br>`triggerBatchDeepDive()` | `POST /api/scraper/trigger`<br>*(mode: item / deep_batch)* | `scraper/fm_collector.py` -> `scrape_product_detail_page()`<br>`scraper/fm_collector.py` -> `parse_fastmoss_detail_api_blobs()`<br>`scraper/fm_collector.py` -> `save_deep_checkpoint()` |
| **数据量化评分与风控**<br>*(入库实时评分 / 配置重算)* | `saveSettingsConfig()`<br>`submitImportProduct()` | `POST /api/config/save`<br>`POST /api/product/add_or_import` | `engine/scorer.py` -> `evaluate_product()`<br>`engine/scorer.py` -> `_is_flagship_or_deep_verified()`<br>`database/db_manager.py` -> `upsert_product()` |
| **AI 研判报告生成与导出** | `runAgentWorkflow()`<br>`copyReportMarkdown()`<br>`copyIdeCommand()` | `POST /api/agent/run` | `engine/ai_analyst.py` -> `generate_workflow_report()` *(写入 `./exports/*.md`)*<br>`database/db_manager.py` -> `save_agent_report()` |
| **高转化主图绘制与导出** | `renderMainImageCanvas()`<br>`downloadCanvasMainImage()` | *前端 Canvas 原生处理* | `static/app.js` -> `downloadCanvasMainImage()` *(导出 `.png`)* |
| **短视频成片录制与导出** | `drawTikTokVideoFrame()`<br>`exportTikTokVerticalVideo()` | *前端 Canvas + MediaRecorder* | `static/app.js` -> `exportTikTokVerticalVideo()` *(导出 `.webm`)* |
| **本土利润测算与寻源** | `runLiveProfitCalc()`<br>`saveProductSourcing()` | `POST /api/profit/calc`<br>`POST /api/product/update_sourcing` | `engine/profit_calc.py` -> `calculate_mexico_profit()`<br>`engine/profit_calc.py` -> `build_1688_search_links()`<br>`database/db_manager.py` -> `update_product_sourcing()` |
| **浏览器油猴实时伴随入库** | `scraper/tampermonkey_bridge.user.js` -> `pushToLocalHub()` | `POST /api/ingest_raw` | `scraper/fm_collector.py` -> `extract_products_from_json_payload()`<br>`database/db_manager.py` -> `upsert_product()` |
| **手动 / CSV 批量导入** | `submitImportProduct()` | `POST /api/product/add_or_import` | `server.py` -> DictReader 解析<br>`database/db_manager.py` -> `upsert_product()` |
