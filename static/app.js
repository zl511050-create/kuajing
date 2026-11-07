// FastMoss AGENT · 墨西哥私有化选品智能体中枢前端交互引擎 (并排并类卡片 + 无人值守防风控巡航 + 旗舰版全量存档)

let STATE = {
  config: {},
  kpis: {},
  products: [],
  reports: [],
  scrape_tasks: [],
  currentReportMarkdown: "",
  currentIdeCommand: "",
  selectedCategory: "ALL",
  selectedSubCategory: "ALL",
  currentPage: 1,
  pageSize: 24,
  displayMode: "grid", // 'grid' (并排卡片) 或 'table' (紧凑表格)
  starredIds: new Set(JSON.parse(localStorage.getItem("fm_starred_ids") || "[]")),
  rejectedIds: new Set(JSON.parse(localStorage.getItem("fm_rejected_ids") || "[]")),
  selectedProductIds: new Set(),
};

function toggleSelectProduct(productId, isChecked) {
  if (isChecked) {
    STATE.selectedProductIds.add(productId);
  } else {
    STATE.selectedProductIds.delete(productId);
  }
  updateBatchActionBar();
}

function getCurrentPageProducts() {
  const filtered = getFilteredProducts();
  const startIdx = (STATE.currentPage - 1) * STATE.pageSize;
  return filtered.slice(startIdx, startIdx + STATE.pageSize);
}

function toggleSelectAllOnPage(masterEl) {
  const isChecked = masterEl.checked;
  const pageProducts = getCurrentPageProducts();
  pageProducts.forEach((p) => {
    if (isChecked) {
      STATE.selectedProductIds.add(p.product_id);
    } else {
      STATE.selectedProductIds.delete(p.product_id);
    }
  });
  document.querySelectorAll(".product-select-chk").forEach((el) => {
    el.checked = isChecked;
  });
  updateBatchActionBar();
}

function updateBatchActionBar() {
  const bar = document.getElementById("floating-batch-bar");
  const countEl = document.getElementById("batch-selected-count");
  if (!bar) return;
  const count = STATE.selectedProductIds.size;
  if (count > 0) {
    bar.style.display = "flex";
    if (countEl) countEl.textContent = count;
  } else {
    bar.style.display = "none";
  }
}

function clearSelectedProducts() {
  STATE.selectedProductIds.clear();
  document.querySelectorAll(".product-select-chk").forEach((el) => {
    el.checked = false;
  });
  const master = document.getElementById("th-select-all");
  if (master) master.checked = false;
  updateBatchActionBar();
}

async function triggerSelectedDeepDive() {
  const pids = Array.from(STATE.selectedProductIds);
  if (pids.length === 0) {
    showToast("请先在表格或卡片中勾选要深潜的商品！");
    return;
  }
  showToast(`🚀 正在为选中的 ${pids.length} 款商品启动静默深潜微巡航...`);
  try {
    const res = await fetch("/api/scraper/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "deep_batch",
        target: pids.join(","),
      }),
    });
    const data = await res.json();
    if (data.status === "ok") {
      showToast(data.message || `已为 ${pids.length} 款选中商品启动后台深潜！`);
      clearSelectedProducts();
      startPollingLiveScrape();
    } else {
      showToast("启动深潜失败: " + data.message);
    }
  } catch (e) {
    showToast("启动深潜失败: " + e.message);
  }
}

function toggleStarProduct(productId) {
  if (STATE.starredIds.has(productId)) {
    STATE.starredIds.delete(productId);
  } else {
    STATE.starredIds.add(productId);
  }
  localStorage.setItem("fm_starred_ids", JSON.stringify([...STATE.starredIds]));
  renderProductsView(false);
}

function rejectProductCard(productId) {
  STATE.rejectedIds.add(productId);
  localStorage.setItem("fm_rejected_ids", JSON.stringify([...STATE.rejectedIds]));
  renderProductsView(false);
}

function filterByShopName(shopName) {
  const kwInput = document.getElementById("filter-keyword");
  if (kwInput) {
    kwInput.value = shopName;
    STATE.selectedCategory = "ALL";
    STATE.selectedSubCategory = "ALL";
    renderProductsView(true);
  }
}

function switchView(viewName) {
  document.querySelectorAll(".view-panel").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));

  const targetView = document.getElementById(`view-${viewName}`);
  if (targetView) targetView.classList.add("active");

  const targetNav = document.getElementById(`nav-${viewName}`);
  if (targetNav) targetNav.classList.add("active");
}

function setProductDisplayMode(mode) {
  STATE.displayMode = mode;
  const gridBox = document.getElementById("products-grid-container");
  const tableBox = document.getElementById("products-table-card");
  const btnGrid = document.getElementById("btn-view-grid");
  const btnTable = document.getElementById("btn-view-table");

  if (mode === "grid") {
    gridBox.style.display = "grid";
    tableBox.style.display = "none";
    btnGrid.classList.add("primary");
    btnTable.classList.remove("primary");
  } else {
    gridBox.style.display = "none";
    tableBox.style.display = "block";
    btnTable.classList.add("primary");
    btnGrid.classList.remove("primary");
  }
}

function selectCategoryFilter(catKey) {
  STATE.selectedCategory = catKey;
  STATE.selectedSubCategory = "ALL";
  STATE.currentPage = 1;
  renderCategoryPills();
  renderProductsView(false);
}

function selectSubCategoryFilter(subCatKey) {
  STATE.selectedSubCategory = subCatKey;
  STATE.currentPage = 1;
  renderCategoryPills();
  renderProductsView(false);
}

function normalizeMainCategory(pOrCat) {
  if (pOrCat && typeof pOrCat === "object") {
    if (pOrCat.main_category && pOrCat.main_category.trim()) {
      return pOrCat.main_category.trim();
    }
    pOrCat = pOrCat.category || "";
  }
  const c = String(pOrCat || "其他类目").trim();
  if (c.includes("美妆") || c.includes("个护") || c.includes("美甲") || c.includes("口红") || c.includes("香水") || c.toLowerCase().includes("belleza")) return "💄 美妆个护与美甲";
  if (c.includes("厨") || c.includes("居") || c.includes("收纳") || c.includes("灯") || c.toLowerCase().includes("hogar") || c.toLowerCase().includes("cocina")) return "🏠 居家日用与厨卫收纳";
  if (c.includes("女装") || c.includes("内衣") || c.includes("塑身") || c.toLowerCase().includes("mujer")) return "👗 女装与塑身内衣";
  if (c.includes("男装") || c.includes("箱包") || c.includes("鞋") || c.includes("配饰") || c.includes("眼镜")) return "👔 男装与箱包配饰";
  if (c.includes("手机") || c.includes("数码") || c.includes("电脑") || c.includes("耳机") || c.includes("电源") || c.toLowerCase().includes("electr")) return "📱 3C数码与手机配件";
  if (c.includes("车") || c.includes("五金") || c.includes("工具") || c.toLowerCase().includes("auto") || c.toLowerCase().includes("herramienta")) return "🚗 汽摩配件与五金工具";
  if (c.includes("宠") || c.includes("玩具") || c.includes("母婴") || c.includes("文具") || c.toLowerCase().includes("mascota")) return "🐾 宠物与玩具文教";
  if (c.includes("运动") || c.includes("户外") || c.includes("露营") || c.includes("健身")) return "🏃 运动户外与露营";
  return "💊 保健与食品百货";
}

function getSubCategory(p) {
  if (p.sub_category && p.sub_category.trim() && !/^\d+$/.test(p.sub_category.trim())) {
    return p.sub_category.trim();
  }
  if (p.category && p.category.trim() && !/^\d+$/.test(p.category.trim())) {
    return p.category.split(">").pop().trim();
  }
  return "综合百货";
}

function renderCategoryPills() {
  const container = document.getElementById("category-pills-container");
  const subContainer = document.getElementById("sub-category-pills-container");
  if (!container) return;

  const hideRisk = document.getElementById("filter-hide-risk")?.checked;
  const basePool = STATE.products.filter(
    (p) => !STATE.rejectedIds.has(p.product_id) && !(hideRisk && (p.is_big_brand || p.risk_level === "HIGH"))
  );

  const catCounts = { ALL: basePool.length };
  basePool.forEach((p) => {
    const mainCat = normalizeMainCategory(p);
    catCounts[mainCat] = (catCounts[mainCat] || 0) + 1;
  });

  // 按商品数量降序排列一级大类
  const sortedMainKeys = Object.keys(catCounts)
    .filter((k) => k !== "ALL")
    .sort((a, b) => (catCounts[b] || 0) - (catCounts[a] || 0));
  const keys = ["ALL", ...sortedMainKeys];

  container.innerHTML = keys
    .map((k) => {
      const label = k === "ALL" ? "🔥 全部类目" : k;
      const activeCls = STATE.selectedCategory === k ? "active" : "";
      return `
        <button class="cat-pill-btn ${activeCls}" onclick="selectCategoryFilter('${k.replace(/'/g, "\\'")}')">
          <span>${label}</span>
          <span class="cnt">${catCounts[k]}</span>
        </button>
      `;
    })
    .join("");

  // 二级细分品类胶囊（当选中某个一级赛道时展开）
  if (subContainer) {
    if (STATE.selectedCategory === "ALL") {
      subContainer.style.display = "none";
      subContainer.innerHTML = "";
    } else {
      const subPool = basePool.filter((p) => normalizeMainCategory(p) === STATE.selectedCategory);
      const subCounts = { ALL: subPool.length };
      subPool.forEach((p) => {
        const sub = getSubCategory(p);
        subCounts[sub] = (subCounts[sub] || 0) + 1;
      });
      const subKeys = [
        "ALL",
        ...Object.keys(subCounts)
          .filter((k) => k !== "ALL")
          .sort((a, b) => subCounts[b] - subCounts[a]),
      ];
      subContainer.style.display = "flex";
      subContainer.innerHTML = subKeys
        .map((sk) => {
          const sLabel = sk === "ALL" ? `📂 全部「${STATE.selectedCategory.slice(2).trim()}」子类目` : sk;
          const sActive = STATE.selectedSubCategory === sk ? "active" : "";
          return `
            <button class="cat-pill-btn ${sActive}" style="padding:4px 10px;font-size:11.5px;" onclick="selectSubCategoryFilter('${sk.replace(/'/g, "\\'")}')">
              <span>${sLabel}</span>
              <span class="cnt">${subCounts[sk]}</span>
            </button>
          `;
        })
        .join("");
    }
  }
}

function renderMarkdown(md) {
  if (!md) return "";
  let html = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const lines = html.split("\n");
  let out = [];
  let inTable = false;
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      if (line.includes("---")) continue;
      const cells = line
        .trim()
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      if (!inTable) {
        out.push("<table><thead><tr>" + cells.map((c) => `<th>${formatInline(c)}</th>`).join("") + "</tr></thead><tbody>");
        inTable = true;
      } else {
        out.push("<tr>" + cells.map((c) => `<td>${formatInline(c)}</td>`).join("") + "</tr>");
      }
      continue;
    } else if (inTable) {
      out.push("</tbody></table>");
      inTable = false;
    }

    if (line.startsWith("### ")) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h3>${formatInline(line.slice(4))}</h3>`);
    } else if (line.startsWith("#### ")) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h4>${formatInline(line.slice(5))}</h4>`);
    } else if (line.trim() === "---") {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<hr style="border:none;border-top:1px dashed #e2e5ec;margin:16px 0;" />`);
    } else if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${formatInline(line.trim().slice(2))}</li>`);
    } else if (/^\d+\.\s+/.test(line.trim())) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${formatInline(line.trim())}</li>`);
    } else if (line.trim() === "") {
      if (inList) { out.push("</ul>"); inList = false; }
    } else {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<p style="margin-bottom:8px;">${formatInline(line)}</p>`);
    }
  }
  if (inTable) out.push("</tbody></table>");
  if (inList) out.push("</ul>");
  return out.join("\n");
}

function formatInline(text) {
  return text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" style="color:#fe2c55;font-weight:600;text-decoration:none;">$1 ↗</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderSparklineSVG(series, isBigBrand) {
  if (!Array.isArray(series) || series.length < 2) {
    series = [8, 12, 10, 14, 13, 15, 14];
  }
  const nums = series.map((v) => {
    if (typeof v === "object" && v !== null) {
      return Number(v.sales || v.units || v.count || 0);
    }
    return Number(v) || 0;
  });
  const w = 98;
  const h = 26;
  const min = Math.min(...nums);
  const max = Math.max(...nums, min + 1);
  const peakIdx = nums.indexOf(max);
  const firstVal = nums[0];
  const lastVal = nums[nums.length - 1];
  const meanVal = nums.reduce((a, b) => a + b, 0) / nums.length;

  // 智能识别 5 种真实 7 日动销形态（彻底告别千篇一律的向上假斜线）
  let morphLabel = "📈爬坡";
  let strokeColor = "#10b981";
  let fillBg = "rgba(16, 185, 129, 0.12)";

  if (isBigBrand) {
    morphLabel = "🏢大牌";
    strokeColor = "#ef4444";
    fillBg = "rgba(239, 68, 68, 0.10)";
  } else if (firstVal === 0 && lastVal > 0) {
    morphLabel = "🆕新上";
    strokeColor = "#00b578";
    fillBg = "rgba(0, 181, 120, 0.14)";
  } else if (peakIdx >= 1 && peakIdx <= 4 && lastVal <= max * 0.68) {
    // 冲高回落：波峰在周中，且第7天比波峰回落超32%
    morphLabel = "⛰️回落";
    strokeColor = "#f59e0b";
    fillBg = "rgba(245, 158, 11, 0.14)";
  } else if (lastVal < firstVal * 0.78) {
    // 动销衰减：首高尾低
    morphLabel = "📉下滑";
    strokeColor = "#ef4444";
    fillBg = "rgba(239, 68, 68, 0.12)";
  } else if (max - min <= Math.max(2, meanVal * 0.35) || Math.abs(lastVal - firstVal) <= meanVal * 0.22) {
    // 存量横盘震荡
    morphLabel = "➖震荡";
    strokeColor = "#3b82f6";
    fillBg = "rgba(59, 130, 246, 0.12)";
  } else if (lastVal >= firstVal * 2.4 && peakIdx >= 5) {
    morphLabel = "🚀脉冲";
    strokeColor = "#00b578";
    fillBg = "rgba(0, 181, 120, 0.15)";
  }

  const coords = nums.map((val, idx) => {
    const x = (idx / (nums.length - 1)) * (w - 8) + 4;
    const y = h - 4 - ((val - min) / (max - min)) * (h - 8);
    return { x: Number(x.toFixed(1)), y: Number(y.toFixed(1)), val };
  });
  const ptsStr = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const areaPtsStr = `4,${h - 2} ${ptsStr} ${w - 4},${h - 2}`;
  const peakCoord = coords[peakIdx] || coords[coords.length - 1];

  return `
    <div style="display:flex;align-items:center;gap:5px;" title="7日逐日动销估算: [${nums.join(", ")}] 单/天 (波峰: ${max}单/天)">
      <span style="font-size:10px;padding:1px 4px;border-radius:4px;background:${fillBg};color:${strokeColor};font-weight:700;white-space:nowrap;">${morphLabel}</span>
      <svg width="${w}" height="${h}" style="overflow:visible;">
        <polygon fill="${fillBg}" points="${areaPtsStr}" />
        <polyline fill="none" stroke="${strokeColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${ptsStr}" />
        <circle cx="${peakCoord.x}" cy="${peakCoord.y}" r="2.4" fill="${strokeColor}" />
      </svg>
      <span style="font-size:11px;color:${strokeColor};font-weight:700;white-space:nowrap;">${firstVal}➔${lastVal}/天</span>
    </div>
  `;
}

function getProductThumbHtml(p, size = 64) {
  let imgUrl = p.image_url || "";
  if (imgUrl && imgUrl.includes("/tt_shop/")) {
    imgUrl = ""; // 过滤误抓的店铺头像
  }
  const mainCat = normalizeMainCategory(p);
  const subCat = getSubCategory(p).slice(0, 4);
  let icon = "📦";
  let bgGrad = "linear-gradient(135deg, #f8fafc, #e2e8f0)";
  let txtColor = "#475569";

  if (mainCat.includes("美妆")) { icon = "💄"; bgGrad = "linear-gradient(135deg, #fff1f2, #ffe4e6)"; txtColor = "#e11d48"; }
  else if (mainCat.includes("居家")) { icon = "🏠"; bgGrad = "linear-gradient(135deg, #ecfdf5, #d1fae5)"; txtColor = "#059669"; }
  else if (mainCat.includes("女装")) { icon = "👗"; bgGrad = "linear-gradient(135deg, #fdf4ff, #fae8ff)"; txtColor = "#c026d3"; }
  else if (mainCat.includes("男装")) { icon = "👔"; bgGrad = "linear-gradient(135deg, #eff6ff, #dbeafe)"; txtColor = "#2563eb"; }
  else if (mainCat.includes("3C")) { icon = "📱"; bgGrad = "linear-gradient(135deg, #eef2ff, #e0e7ff)"; txtColor = "#4f46e5"; }
  else if (mainCat.includes("汽摩")) { icon = "🚗"; bgGrad = "linear-gradient(135deg, #fff7ed, #ffedd5)"; txtColor = "#ea580c"; }
  else if (mainCat.includes("宠物")) { icon = "🐾"; bgGrad = "linear-gradient(135deg, #fefce8, #fef08a)"; txtColor = "#ca8a04"; }
  else if (mainCat.includes("运动")) { icon = "🏃"; bgGrad = "linear-gradient(135deg, #f0fdf4, #bbf7d0)"; txtColor = "#16a34a"; }
  else if (mainCat.includes("保健")) { icon = "💊"; bgGrad = "linear-gradient(135deg, #f0f9ff, #bae6fd)"; txtColor = "#0284c7"; }

  const fallbackHtml = `<div class=\\'prod-thumb-placeholder\\' style=\\'width:${size}px;height:${size}px;background:${bgGrad};color:${txtColor};flex-direction:column;gap:2px;\\'><span style=\\'font-size:${Math.round(size * 0.36)}px;line-height:1;\\'>${icon}</span><span style=\\'font-size:9.5px;font-weight:700;\\'>${subCat}</span></div>`;

  if (imgUrl) {
    return `<img src="${imgUrl}" class="prod-thumb" style="width:${size}px;height:${size}px;" loading="lazy" alt="thumb" onerror="this.outerHTML='${fallbackHtml}'" />`;
  }
  return `<div class="prod-thumb-placeholder" style="width:${size}px;height:${size}px;background:${bgGrad};color:${txtColor};flex-direction:column;gap:2px;"><span style="font-size:${Math.round(size * 0.36)}px;line-height:1;">${icon}</span><span style="font-size:9.5px;font-weight:700;">${subCat}</span></div>`;
}

// 获取 1688 搜索直达链接：
// 1. 优先使用后端预计算好的 UTF-8 搜索链接 (p.links_1688.keyword_links[0].url)；
// 2. 若无后端预计算链接，前端直接提取中文搜索词进行 UTF-8 编码，并显式携带 _input_charset=utf-8&n=y，通知 1688 按 UTF-8 解码。
function get1688SearchUrl(p) {
  if (p && p.links_1688 && Array.isArray(p.links_1688.keyword_links) && p.links_1688.keyword_links.length > 0) {
    const valid = p.links_1688.keyword_links.find((k) => k && k.url);
    if (valid && valid.url) return valid.url;
  }
  let kw = (p && Array.isArray(p.keywords_1688) && p.keywords_1688[0]) || (p && (p.title_cn || p.title)) || "";
  if (kw && typeof kw === "string" && kw.trim()) {
    kw = kw.replace(/^[【\[].*?[】\]]\s*/, "");
    if (kw.includes(">")) kw = kw.split(">").pop().trim();
    return `https://s.1688.com/selloffer/offer_search.htm?keywords=${encodeURIComponent(kw.trim())}&_input_charset=utf-8&n=y`;
  }
  return "https://s.1688.com/";
}

// 自动调用本地对应商品保存的主图去 1688 进行以图搜款（高清大图优先策略）
async function search1688ByImage(productId) {
  const p = STATE.products.find((item) => item.product_id === productId);
  if (!p) {
    showToast("⚠️ 未找到对应商品数据");
    return;
  }

  // 1. 高清优先解析：优先使用 540P 实拍高清大图，无大图则自动降级使用列表缩略图
  let targetImg = p.image_large_url || "";
  let isCandidateHd = Boolean(targetImg);
  if (!targetImg || targetImg.includes("mx.svg")) {
    if (p.image_url && p.image_url.startsWith("/thumbs/") && !p.image_url.includes("_large")) {
      targetImg = p.image_url.replace(/\.([a-zA-Z0-9]+)$/, "_large.$1");
      isCandidateHd = true;
    } else {
      targetImg = p.image_url || "";
      isCandidateHd = false;
    }
  }

  if (!targetImg || targetImg.includes("mx.svg")) {
    showToast("⚠️ 该商品暂无有效主图，将为您打开 1688 关键词搜索");
    window.open(get1688SearchUrl(p), "_blank");
    return;
  }

  // 2. 若图片原本是公网可访问的 HTTP(S) 地址（且不是本地 127.0.0.1 / localhost），直接使用 1688 有源搜图接口
  const isPublicUrl = /^https?:\/\//i.test(targetImg) && !targetImg.includes("127.0.0.1") && !targetImg.includes("localhost");
  if (isPublicUrl) {
    showToast(`🚀 正在通过商品${isCandidateHd ? "高清" : ""}主图直达 1688 以图搜款...`);
    const searchUrl = `https://s.1688.com/youyuan/index.htm?tab=all&imageAddress=${encodeURIComponent(targetImg)}`;
    window.open(searchUrl, "_blank");
    return;
  }

  // 3. 本地保存的私有主图（如 /thumbs/xxx.jpg 或 /thumbs/xxx_large.jpg）
  // 最佳交互方案：将高清主图按原始天然分辨率读取并写入用户系统剪贴板，随后在新标签唤起 1688
  // 用户在 1688 搜索框按一次 Ctrl+V (Mac 下 Cmd+V) 即可实现高清保真以图搜款！
  try {
    showToast(isCandidateHd ? "⏳ 正在读取 540P 高清原图写入剪贴板..." : "⏳ 正在读取本地主图写入剪贴板...");
    let imgResp;
    let usedHd = isCandidateHd;
    try {
      imgResp = await fetch(targetImg);
      if (!imgResp.ok && isCandidateHd && p.image_url && p.image_url !== targetImg) {
        imgResp = await fetch(p.image_url);
        usedHd = false;
      }
    } catch (fetchErr) {
      if (p.image_url && p.image_url !== targetImg) {
        imgResp = await fetch(p.image_url);
        usedHd = false;
      } else {
        throw fetchErr;
      }
    }

    const blob = await imgResp.blob();

    const imgEl = new Image();
    imgEl.crossOrigin = "anonymous";
    const imgLoaded = new Promise((resolve, reject) => {
      imgEl.onload = resolve;
      imgEl.onerror = reject;
      imgEl.src = URL.createObjectURL(blob);
    });
    await imgLoaded;

    // 保留图片原始天然高清像素尺寸（不强制缩小，防止糊图）
    const canvas = document.createElement("canvas");
    canvas.width = imgEl.naturalWidth || 540;
    canvas.height = imgEl.naturalHeight || 540;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(imgEl, 0, 0);

    canvas.toBlob(async (pngBlob) => {
      if (pngBlob && navigator.clipboard && window.ClipboardItem) {
        try {
          await navigator.clipboard.write([
            new ClipboardItem({ "image/png": pngBlob }),
          ]);
          window.open("https://s.1688.com/", "_blank");
          showToast(
            usedHd
              ? "📋 【540P高清实拍图】已复制到剪贴板！已为您打开 1688，在搜索框直接按 Ctrl+V (Cmd+V) 即可精准搜同款！"
              : "📋 主图已复制到剪贴板！已为您打开 1688，在搜索框直接按 Ctrl+V (Cmd+V) 即可秒级以图搜款！"
          );
          return;
        } catch (clipErr) {
          console.warn("Clipboard write error:", clipErr);
        }
      }
      // 平稳降级方案：新标签打开图片和 1688，引导用户拖拽
      window.open(targetImg, "_blank");
      window.open("https://s.1688.com/", "_blank");
      showToast("💡 已打开本地高清图与 1688，可直接拖拽主图到 1688 搜图框进行搜款！");
    }, "image/png");
  } catch (err) {
    console.error("以图搜图调用异常:", err);
    window.open("https://s.1688.com/", "_blank");
    showToast("⚠️ 本地主图读取异常，已打开 1688 首页");
  }
}

async function loadDashboardData(sortVal = "") {
  try {
    const currentSort = sortVal || document.getElementById("filter-sort")?.value || "score";
    const resp = await fetch(`/api/dashboard?sort=${encodeURIComponent(currentSort)}`);
    const data = await resp.json();
    if (data.status !== "ok") return;

    STATE.config = data.config || {};
    STATE.kpis = data.kpis || {};
    STATE.products = data.products || [];
    STATE.reports = data.reports || [];
    STATE.scrape_tasks = data.scrape_tasks || [];

    document.getElementById("nav-prod-count").textContent = STATE.kpis.clean_candidates || 0;
    document.getElementById("kpi-total").textContent = STATE.kpis.total_products || 0;
    document.getElementById("kpi-clean").textContent = STATE.kpis.clean_candidates || 0;
    document.getElementById("kpi-stier").textContent = STATE.kpis.s_tier_count || 0;
    document.getElementById("kpi-filtered").textContent = STATE.kpis.filtered_risk_count || 0;

    if (STATE.config?.scraper_settings) {
      const s = STATE.config.scraper_settings;
      if (s.start_page) {
        const sp = document.getElementById("top-scrape-start-page");
        const sp2 = document.getElementById("scraper-start-page");
        const ssp = document.getElementById("search-start-page");
        if (sp) sp.value = s.start_page;
        if (sp2) sp2.value = s.start_page;
        if (ssp) ssp.value = s.search_start || s.start_page;
      }
      if (s.pages) {
        const ps = document.getElementById("top-scrape-pages-select");
        const ps2 = document.getElementById("scraper-pages-select");
        const smp = document.getElementById("search-max-pages");
        if (ps) ps.value = s.pages;
        if (ps2) ps2.value = s.pages;
        if (smp) smp.value = s.search_pages || s.pages;
      }
      const badge = document.getElementById("settings-locked-badge");
      if (badge && s.start_page) {
        badge.style.display = "inline-flex";
        badge.innerHTML = `✅ 已锁定: 第 ${s.start_page} 页起抓到 ${s.pages || 500} 页`;
      }
    }

    populateProductSelectors();
    renderRecentReportsSidebar();
    renderCategoryPills();
    renderProductsView(false);
    renderScrapeTasksTable();
    renderKanbanBoard();
    onSelectCalcProduct();

    if (!STATE.currentReportMarkdown) {
      if (STATE.reports.length > 0) {
        displayReport(STATE.reports[0]);
      } else {
        runAgentWorkflow("potential_discovery");
      }
    }
  } catch (err) {
    console.error("Dashboard load error:", err);
  }
}

async function onSortChange() {
  const sortMode = document.getElementById("filter-sort")?.value || "score";
  STATE.currentPage = 1;
  await loadDashboardData(sortMode);
  renderProductsView(true);
}

function populateProductSelectors() {
  const agentSel = document.getElementById("agent-product-selector");
  const calcSel = document.getElementById("calc-product-select");
  const tboxSel = document.getElementById("toolbox-product-select");
  const prevAgentVal = agentSel ? agentSel.value : "";
  const prevCalcVal = calcSel ? calcSel.value : "";
  const prevTboxVal = tboxSel ? tboxSel.value : "";

  if (agentSel) agentSel.innerHTML = `<option value="">@ 选择本地库商品做单品尽调 (默认自动选最高分潜力品)</option>`;
  if (calcSel) calcSel.innerHTML = "";
  if (tboxSel) tboxSel.innerHTML = "";

  STATE.products.forEach((p) => {
    const label = `[${p.potential_score}分] ${p.title_cn || p.title} ($${p.price_mxn} MXN)`;
    if (agentSel) {
      const opt1 = document.createElement("option");
      opt1.value = p.product_id;
      opt1.textContent = label;
      agentSel.appendChild(opt1);
    }
    if (calcSel) {
      const opt2 = document.createElement("option");
      opt2.value = p.product_id;
      opt2.textContent = label;
      calcSel.appendChild(opt2);
    }
    if (tboxSel) {
      const opt3 = document.createElement("option");
      opt3.value = p.product_id;
      opt3.textContent = label;
      tboxSel.appendChild(opt3);
    }
  });

  if (prevAgentVal && agentSel) agentSel.value = prevAgentVal;
  if (prevCalcVal && calcSel) calcSel.value = prevCalcVal;
  if (prevTboxVal && tboxSel) tboxSel.value = prevTboxVal;
}

function renderRecentReportsSidebar() {
  const box = document.getElementById("recent-reports-list");
  if (!STATE.reports.length) {
    box.innerHTML = `<div class="recent-item">暂无历史记录，点击右侧任务卡片立即生成</div>`;
    return;
  }
  box.innerHTML = STATE.reports
    .map(
      (r, idx) => `
      <div class="recent-item" onclick="showSavedReport(${idx})" title="${r.title}">
        📄 ${r.title}
      </div>
    `
    )
    .join("");
}

function showSavedReport(idx) {
  const r = STATE.reports[idx];
  if (!r) return;
  switchView("agent");
  displayReport(r);
}

function displayReport(r) {
  document.getElementById("report-title").textContent = r.title || "墨西哥智能体选品分析报告";
  document.getElementById("report-meta").textContent = `生成时间: ${r.created_at || "刚刚"} | 数据引擎: 本地五维量化评分 + 墨西哥空海运成本精算`;
  STATE.currentReportMarkdown = r.report_markdown || "";
  document.getElementById("report-markdown-content").innerHTML = renderMarkdown(STATE.currentReportMarkdown);

  if (r.ide_export_file) {
    const bridgeBox = document.getElementById("ide-bridge-box");
    bridgeBox.style.display = "flex";
    document.getElementById("ide-export-path").textContent = r.ide_export_file;
    STATE.currentIdeCommand = `请读取 ${r.ide_export_file} 并帮我做深度选品策略诊断、1688源头厂压价话术及墨西哥西语短视频带货脚本拆解`;
  }
}

const PROMPT_TEMPLATES = {
  potential_discovery:
    "我是【墨西哥 TikTok Shop】卖家，目前暂无固定货盘，计划采用「100件空运快速测款 ➔ 500件海运本地仓囤货」模式。请帮我从本地商品库的新品榜/飙升榜中筛选最适合起步的 Top 潜力商品：重点拆解近7天动销爬坡斜率、黄金价格带（150~680 MXN）、关联中小达人出单结构，并标出哪些是处于陡峭上升期的新品、哪些是受大牌垄断或单一头部达人偶然带爆的伪机会。",
  blue_ocean_scan:
    "我想做【墨西哥】本土囤货但还没最终敲定主攻类目。请帮我对本地选品库进行二级细分小类目交叉聚类：找出近 7~28 天销量增速快、同款竞争店铺数量少、且属于免认证轻小件普货的 Top 5 蓝海细分赛道，并给出每个赛道的代表标杆商品、建议切入定价区间（MXN）以及 1688 源头拿货成本红线。",
  low_barrier_entry:
    "请聚焦免除墨西哥 NOM 强电认证与 COFEPRIS 卫生许可、单件重量 <450g 的轻小件高毛利功能品，为我拆解 3~4 个低资金门槛切入方向：对比竞品差评痛点微创新空间、中小达人寄样带货难度、商品卡自然流占比，并测算首批 100 件空运测款压货资金与海运放大后的净利率。",
  product_due_diligence:
    "请对当前选中的 @商品 做一份完整的 TikTok Shop 墨西哥单品立项尽调报告：涵盖目标消费人群画像、西语高频痛点搜索词、单件引流装 vs 组合利润装定价策略、前3秒带货短视频脚本公式、1688 源头工厂寻源链接以及空运测款/海运囤货双阶段毛利核算。",
  voc_micro_innovation:
    "请深度拆解当前 @商品 在墨西哥本土买家中的高频差评痛点（如：材质单薄、尺寸不合拉美体型/车型、缺少西语图文说明卡、物流外包装破损、配件不够用），并给出 3 套低成本（单件增加成本 < ¥2.5 RMB）的 1688 差异化微创新与「主品+高感知赠品组合装」方案，帮我避开同款低价内卷并把售价提高 15%~25%。",
  sourcing_negotiation:
    "请基于当前 @商品 的墨西哥前台售价（MXN）、预估克重与空海运头程及本土 3PL 尾程费用，倒推 1688 源头工厂拿货目标红线价。并帮我编写一套向 1688 实力工厂询盘砍价的专业话术（含：首单 100 件贴牌测款支持、后续 500~2000 件阶梯降价承诺、压缩外包装体积重防抛货要求、以及出厂必检质检清单）。",
  shop_benchmarking:
    "请对本地选品库中上榜商品最多、动销最强的【墨西哥标杆黑马店铺】进行货盘逆向拆解：分析它们的店铺主营类目集中度、「引流爆款 + 高毛利利润款」价格带矩阵配合、达人联盟佣金率设置规律，并给出我作为新店抄作业搭建首批 5~8 款测款货盘的组合建议。",
  es_video_script:
    "请针对当前 @商品，结合墨西哥本土生活场景与拉美消费者审美，编写 3 套高转化 TikTok 带货短视频分镜脚本（1. 强痛点前后对比型 Before/After；2. 沉浸式解压/功能实测型；3. 墨西哥家庭/情侣真实生活开箱型）。每套脚本需包含：前 3 秒黄金视觉钩子、地道墨西哥西语口播台词（附中文翻译）、画面拍摄指导及结尾引导点击左下角小黄车促单话术。",
  seo_listing_listing:
    "为了吃透墨西哥 TikTok Shop 商城搜索与商品卡自然流量，请为当前 @商品 策划全套西语 Listing 方案：1. 包含核心热搜词与痛点场景词的高点击西语 SEO 标题（3个备选）；2. 10 个墨西哥买家高频搜索的西语长尾属性词；3. 5 张主图与详情页的视觉构图企划及图片内嵌西语卖点文案（突出 Envío rápido desde México 本土仓极速达）。",
  mexico_seasonal_plan:
    "请结合墨西哥全年核心电商大促与季节性消费特征（如：5月母亲节 Día de las Madres、5月底 Hot Sale 大促、6~9月雨季防潮与返校季 Regreso a Clases、10~11月亡灵节与 Buen Fin 墨西哥黑五、12月圣诞礼赠季），扫描本地选品库中哪些细分品类最适合提前卡位，并按「空运提前 15 天 / 海运提前 45 天」倒推备货截单时间表。",
  creator_outreach_es:
    "请针对当前 @商品 制定墨西哥本土达人（Affiliate）建联寄样方案：1. 明确最易出单的达人画像（粉丝量级 5K~100K 腰尾部达人、内容垂类标签、近30天GPM要求）；2. 编写 3 套地道、热情的墨西哥西语达人建联邀约话术（含 TikTok 私信首联免费寄样话术、WhatsApp 样品物流跟进与脚本建议话术、收样后温和催发视频话术，均附中酉对照）。",
  compliance_risk_audit:
    "请对当前 @商品 及本地选品库进行【墨西哥海关清关与平台合规排雷体检】：逐项核查是否涉及 NOM 强制认证（带插头/高压电器/儿童玩具）、IFETEL 无线蓝牙射频认证、COFEPRIS 医疗器械/化妆品/入口保健品卫生许可、外观专利或国际大牌商标侵权风险，并给出安全报关品名建议与头程物流渠道（普货空海运 vs 敏感货专线）选择指南。",
};

function filterPromptLibrary(cat, btnEl) {
  if (btnEl) {
    document.querySelectorAll("#prompt-cat-pills .cat-pill-btn").forEach((b) => b.classList.remove("active"));
    btnEl.classList.add("active");
  }
  document.querySelectorAll("#prompt-library-grid .prompt-card").forEach((card) => {
    const pcat = card.getAttribute("data-pcat");
    if (cat === "ALL" || pcat === cat) {
      card.style.display = "flex";
    } else {
      card.style.display = "none";
    }
  });
}

function usePromptTemplate(workflowKey, runNow = true) {
  const tpl = PROMPT_TEMPLATES[workflowKey] || "";
  const inputEl = document.getElementById("agent-custom-input");
  if (inputEl && tpl) {
    inputEl.value = tpl;
    inputEl.focus();
  }
  if (runNow) {
    runAgentWorkflow(workflowKey);
  }
}

async function runAgentWorkflow(workflowType, forcedProductId = "") {
  switchView("agent");
  const productId = forcedProductId || document.getElementById("agent-product-selector").value;
  const customQuery = document.getElementById("agent-custom-input").value;

  document.getElementById("report-title").textContent = "⏳ 智能体正在扫描本地墨西哥商品库并核算 1688 毛利...";
  document.getElementById("report-markdown-content").innerHTML = `<p style="color:var(--fm-pink);font-weight:600;">正在执行五维量化评分、去大牌过滤与空运/海运双阶段利润建模...</p>`;
  const reportBox = document.getElementById("agent-report-container");
  if (reportBox) reportBox.scrollIntoView({ behavior: "smooth", block: "nearest" });

  try {
    const resp = await fetch("/api/agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow_type: workflowType,
        product_id: productId,
        custom_query: customQuery,
      }),
    });
    const data = await resp.json();
    if (data.status === "ok" && data.report) {
      displayReport(data.report);
      loadDashboardData();
    }
  } catch (err) {
    console.error("Workflow error:", err);
  }
}

// 统一渲染选品库（同时更新并排卡片网格、紧凑表格与极速分页条）
function resetPageAndRender() {
  renderProductsView(true);
}

// 按当前筛选/排序条件返回完整商品列表（不分页），供渲染与批量深潜共用
function getFilteredProducts() {
  const hideRisk = document.getElementById("filter-hide-risk")?.checked;
  const presetFilter = document.getElementById("filter-preset")?.value || "ALL";
  const tierFilter = document.getElementById("filter-tier")?.value || "ALL";
  const sortMode = document.getElementById("filter-sort")?.value || "score";
  const kw = (document.getElementById("filter-keyword")?.value || "").toLowerCase().trim();

  let filtered = STATE.products.filter((p) => {
    if (STATE.rejectedIds.has(p.product_id)) return false;
    if (hideRisk && (p.is_big_brand || p.risk_level === "HIGH")) return false;
    if (STATE.selectedCategory !== "ALL" && normalizeMainCategory(p) !== STATE.selectedCategory) {
      return false;
    }
    if (STATE.selectedSubCategory !== "ALL" && getSubCategory(p) !== STATE.selectedSubCategory) {
      return false;
    }
    if (tierFilter === "S" && p.potential_score < 82) return false;
    if (tierFilter === "A" && p.potential_score < 72) return false;

    // 量化策略预设筛选
    if (presetFilter === "FLAGSHIP_ONLY" && !(Number(p.deep_scraped) === 1 || p.radar_scores?.score_tier === "FLAGSHIP_VERIFIED")) return false;
    if (presetFilter === "UNSCRAPED_S" && !(Number(p.deep_scraped) !== 1 && p.potential_score >= 72)) return false;
    if (presetFilter === "GOLDEN" && !(p.price_mxn >= 150 && p.price_mxn <= 680 && p.sales_7d >= 20)) return false;
    if (presetFilter === "HIGH_PRICE" && !(p.price_mxn >= 260 && p.sales_7d >= 30)) return false;
    if (presetFilter === "NEW_BURST" && !(p.days_online <= 15 && p.sales_7d >= 10)) return false;
    if (presetFilter === "HAS_IMG" && (!p.image_url || p.image_url.includes("/tt_shop/"))) return false;
    if (presetFilter === "STARRED" && !STATE.starredIds.has(p.product_id)) return false;

    if (kw) {
      const text = `${p.product_id} ${p.title_cn} ${p.title_es} ${p.main_category || ""} ${p.sub_category || ""} ${p.category} ${p.shop_name}`.toLowerCase();
      if (!text.includes(kw)) return false;
    }
    return true;
  });

  // 排序逻辑（数值字段统一转 Number，避免字符串比较导致排序失效）
  const num = (v) => Number(v) || 0;
  const releaseTs = (p) => {
    const t = Date.parse(p.release_date || "");
    if (!isNaN(t)) return t;
    const d = Number(p.days_online);
    return isNaN(d) || d <= 0 ? 0 : Date.now() - d * 86400000;
  };
  filtered.sort((a, b) => {
    if (sortMode === "sales") return num(b.sales_7d) - num(a.sales_7d);
    if (sortMode === "total_sales") return num(b.total_sales) - num(a.total_sales);
    if (sortMode === "newest") return releaseTs(b) - releaseTs(a);
    if (sortMode === "price_asc") return num(a.price_mxn) - num(b.price_mxn);
    if (sortMode === "price_desc") return num(b.price_mxn) - num(a.price_mxn);
    return num(b.potential_score) - num(a.potential_score);
  });
  return filtered;
}

function renderProductsView(resetPage = true) {
  if (resetPage) STATE.currentPage = 1;
  renderCategoryPills();

  const filtered = getFilteredProducts();

  const totalCount = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / STATE.pageSize));
  if (STATE.currentPage > totalPages) STATE.currentPage = totalPages;

  const startIdx = (STATE.currentPage - 1) * STATE.pageSize;
  const pageItems = filtered.slice(startIdx, startIdx + STATE.pageSize);

  renderProductsGrid(pageItems, totalCount);
  renderProductsTable(pageItems, totalCount);
  renderPaginationBar(totalCount, totalPages);
}

function goToProductPage(pageNum) {
  STATE.currentPage = pageNum;
  renderProductsView(false);
  const gridBox = document.getElementById("products-grid-container");
  if (gridBox) gridBox.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderPaginationBar(totalCount, totalPages) {
  const bar = document.getElementById("pagination-container");
  if (!bar) return;
  if (totalCount <= STATE.pageSize) {
    bar.innerHTML = `<span style="font-size:12px;color:var(--text-secondary);">共匹配 <strong>${totalCount}</strong> 件墨西哥商品（已全部展示）</span>`;
    return;
  }

  let btns = [];
  btns.push(
    `<button class="btn-sm" ${STATE.currentPage <= 1 ? "disabled" : ""} onclick="goToProductPage(${STATE.currentPage - 1})">⬅️ 上一页</button>`
  );

  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || Math.abs(p - STATE.currentPage) <= 2) {
      const activeStyle = p === STATE.currentPage ? "background:var(--fm-pink);color:#fff;border-color:var(--fm-pink);" : "";
      btns.push(`<button class="btn-sm" style="${activeStyle}" onclick="goToProductPage(${p})">${p}</button>`);
    } else if (btns[btns.length - 1] !== `<span style="color:var(--text-muted);">...</span>`) {
      btns.push(`<span style="color:var(--text-muted);">...</span>`);
    }
  }

  btns.push(
    `<button class="btn-sm" ${STATE.currentPage >= totalPages ? "disabled" : ""} onclick="goToProductPage(${STATE.currentPage + 1})">下一页 ➡️</button>`
  );

  bar.innerHTML = `
    <span style="font-size:12px;color:var(--text-secondary);margin-right:8px;">
      共匹配 <strong>${totalCount}</strong> 件商品 · 第 <strong>${STATE.currentPage}/${totalPages}</strong> 页（每页 ${STATE.pageSize} 件）
    </span>
    ${btns.join("")}
  `;
}

// 渲染并排高密度商品卡片网格 (每行 3~4 张)
function renderProductsGrid(filtered, totalCount = 0) {
  const gridBox = document.getElementById("products-grid-container");
  if (!gridBox) return;

  if (!filtered.length) {
    gridBox.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:40px;background:#fff;border-radius:16px;color:var(--text-muted);">当前分类/筛选条件下暂无商品，可切换上方类目胶囊或点击右上角「🛳️ 开启无人值守连续抓数」。</div>`;
    return;
  }

  gridBox.innerHTML = filtered
    .map((p) => {
      let scoreClass = "score-b";
      if (p.potential_score >= 80) scoreClass = "score-s";
      else if (p.potential_score >= 70) scoreClass = "score-a";
      else if (p.potential_score < 56) scoreClass = "score-c";

      const pe = p.profit_eval || {};
      const seaM = pe.sea_scale_stage ? pe.sea_scale_stage.margin_pct : 0;
      const fmUrl = p.fastmoss_url || `https://www.fastmoss.com/zh/e-commerce/detail/${p.product_id}`;
      const firstKwLink = get1688SearchUrl(p);

      const relDate = p.release_date || `近${p.days_online || 15}天`;
      const shopSalesTxt = p.shop_total_sales ? `(${p.shop_total_sales})` : "";
      const subCatLabel = getSubCategory(p);
      const isStarred = STATE.starredIds.has(p.product_id);
      const starBtnTxt = isStarred ? "⭐" : "☆";
      const starStyle = isStarred ? "background:#fef3c7;color:#d97706;border-color:#fde68a;" : "";

      const isFlagshipVerified = p.deep_scraped || (p.creators_7d && p.creators_7d > 0 && p.creators_7d !== 8);
      const dataTierChip = isFlagshipVerified
        ? `<span class="tag-chip" style="background:#fef3c7;color:#b45309;font-weight:700;" title="已穿透获取完整达人/曲线数据">👑 旗舰实测</span>`
        : `<span class="tag-chip" style="background:#f1f5f9;color:#475569;" title="标准版自适应动销与毛利建模（点击右侧🔬深潜可穿透详情页）">📊 标准建模</span>`;

      const compTags = Array.isArray(p.compliance_tags) ? p.compliance_tags : [];
      const primaryCompTag = compTags[0] || "✅ 普货";
      const isLowPriceTrap = p.price_mxn < 130;
      const compStyle = isLowPriceTrap || p.risk_level === "HIGH"
        ? "background:#fef2f2;color:#dc2626;font-weight:700;"
        : "background:#ecfdf5;color:#059669;";

      const deltaBadge =
        p.delta_sales && p.delta_sales > 0
          ? `<span class="tag-chip" style="background:#ecfdf5;color:#059669;font-weight:700;">📈 增量 +${p.delta_sales}单</span>`
          : "";

      return `
        <div class="prod-grid-card" style="position:relative;${isStarred ? "border-color:#f59e0b;box-shadow:0 6px 18px rgba(245,158,11,0.12);" : ""}">
          <input type="checkbox" class="product-select-chk" data-pid="${p.product_id}" onchange="toggleSelectProduct('${p.product_id}', this.checked)" ${STATE.selectedProductIds.has(p.product_id) ? "checked" : ""} style="position:absolute;top:8px;left:8px;width:17px;height:17px;cursor:pointer;z-index:5;" title="勾选加入批量深潜" />
          <div>
            <!-- 顶部：主图 + 评分 + 标题 -->
            <div class="pgc-header">
              <div class="pgc-thumb-wrap">
                ${getProductThumbHtml(p, 68)}
                <span class="pgc-board-badge">${subCatLabel.slice(0, 6)}</span>
              </div>
              <div class="pgc-title-box">
                <div class="pgc-top-badges">
                  <div style="display:flex;align-items:center;gap:4px;">
                    <span class="score-pill ${scoreClass}">${p.potential_score}分 · ${p.tier.split("·")[0]}</span>
                    ${dataTierChip}
                  </div>
                  <div style="display:flex;gap:3px;">
                    <button class="btn-sm" style="padding:2px 5px;font-size:10.5px;background:#f0fdf4;color:#166534;border-color:#bbf7d0;font-weight:700;" onclick="openProductDetailModal('${p.product_id}')" title="以常规专业商品网页形式查看全维数据">🛍️主页</button>
                    <button class="btn-sm" style="padding:2px 5px;font-size:10.5px;background:#eef2ff;color:#4f46e5;border-color:#c7d2fe;" onclick="triggerSingleDeepDive('${p.product_id}')" title="靶向深潜该商品详情页，抓取实拍主图与达人视频矩阵">🔬深潜</button>
                    <button class="btn-sm" style="padding:2px 5px;font-size:10.5px;background:#fff0f4;color:var(--fm-pink);border-color:#ffd6e0;" onclick="openToolbox('voc_insight', '${p.product_id}')" title="用 AI 工具箱处理该商品">✨AI</button>
                    <button class="btn-sm" style="padding:2px 5px;font-size:10.5px;${starStyle}" onclick="toggleStarProduct('${p.product_id}')" title="一键加入星标备选池">${starBtnTxt}</button>
                    <button class="btn-sm" style="padding:2px 5px;font-size:10.5px;" onclick="openRawJsonModal('${p.product_id}')" title="查看网页全量原始存档">🗂️</button>
                    <button class="btn-sm" style="padding:2px 4px;font-size:10.5px;color:#94a3b8;" onclick="rejectProductCard('${p.product_id}')" title="一键排除该商品">✕</button>
                  </div>
                </div>
                <div class="pgc-title-cn" title="${p.title_cn || p.title}">${p.title_cn || p.title}</div>
                <div class="pgc-title-es" title="${p.title_es || ""}">${p.title_es || ""}</div>
              </div>
            </div>

            <!-- 核心元数据条：上架日期 + 所属店铺（点击可以店选品） + 品类克重 + 合规/低客单提示 -->
            <div class="pgc-meta-row">
              <span>📅 ${relDate}</span>
              <span style="cursor:pointer;color:#1677ff;" onclick="filterByShopName('${(p.shop_name || "").replace(/'/g, "\\'")}')" title="点击筛选该店铺名下所有上榜商品（以店选品）">🏪 <strong>${p.shop_name}</strong> ${shopSalesTxt} 🔍</span>
              <span>⚖️ 约${p.weight_g || 200}g (拿货¥${p.cost_1688_rmb})</span>
              <span class="tag-chip" style="${compStyle}">${primaryCompTag}</span>
              ${deltaBadge}
            </div>

            <!-- 核心价格与销量三宫格 -->
            <div class="pgc-metrics-grid">
              <div class="pgc-metric-cell">
                <div class="pgc-metric-label">售卖价格 (MXN)</div>
                <div class="pgc-metric-val" style="color:var(--fm-pink);">$${p.price_mxn}</div>
                <div style="font-size:10.5px;color:var(--text-muted);">≈ ¥${pe.revenue_rmb || "--"} RMB</div>
              </div>
              <div class="pgc-metric-cell">
                <div class="pgc-metric-label">近7天销量 / 增速</div>
                <div class="pgc-metric-val">${p.sales_7d} 单</div>
                <div style="font-size:10.5px;color:#059669;font-weight:700;">+${p.growth_rate_7d}%</div>
              </div>
              <div class="pgc-metric-cell">
                <div class="pgc-metric-label">总销量 / 海运净利</div>
                <div class="pgc-metric-val">${p.total_sales} 单</div>
                <div style="font-size:10.5px;color:#1677ff;font-weight:700;">净利 ${seaM}%</div>
              </div>
            </div>

            <!-- 7天动销形态迷你曲线 -->
            <div class="pgc-curve-bar">
              <span style="font-size:11px;font-weight:600;color:#475569;">📊 7日趋势</span>
              ${renderSparklineSVG(p.daily_sales_series, p.is_big_brand)}
            </div>
          </div>

          <!-- 底部专业商品网页与核心操作按钮 -->
          <div class="pgc-actions">
            <button class="btn-sm primary" style="background:#161823;border-color:#161823;color:#fff;font-weight:700;" onclick="openProductDetailModal('${p.product_id}')" title="以专业电商商品网页的形式查看该商品全部深度提取数据">
              🛍️ 专业主页
            </button>
            <a href="${fmUrl}" target="_blank" class="btn-sm" style="text-decoration:none;text-align:center;" title="在新标签页打开 FastMoss 该商品详情原网页">
              🔗 网页 ↗
            </a>
            <button class="btn-sm" onclick="jumpToDueDiligence('${p.product_id}')">🎯 @尽调</button>
            <a href="${firstKwLink}" target="_blank" class="btn-sm" style="text-decoration:none;text-align:center;" title="按关键词直达 1688 货源">🏭 1688</a>
            <button class="btn-sm" onclick="search1688ByImage('${p.product_id}')" title="自动调用本地商品主图去 1688 以图搜款">🖼️ 图搜</button>
            <button class="btn-sm" onclick="jumpToCalc('${p.product_id}')">🧮 测款</button>
          </div>
        </div>
      `;
    })
    .join("");
}

// 渲染紧凑表格视图
function renderProductsTable(filtered, totalCount = 0) {
  const tbody = document.getElementById("products-table-body");
  if (!tbody) return;
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:30px;color:var(--text-muted);">未找到符合当前筛选条件的商品。</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map((p) => {
      let scoreClass = "score-b";
      if (p.potential_score >= 82) scoreClass = "score-s";
      else if (p.potential_score >= 72) scoreClass = "score-a";
      else if (p.potential_score < 58) scoreClass = "score-c";

      const pe = p.profit_eval || {};
      const airM = pe.air_test_stage ? pe.air_test_stage.margin_pct : 0;
      const seaM = pe.sea_scale_stage ? pe.sea_scale_stage.margin_pct : 0;
      const fmUrl = p.fastmoss_url || `https://www.fastmoss.com/zh/e-commerce/detail/${p.product_id}`;
      const firstKwLink = get1688SearchUrl(p);

      const isFlagshipTier = p.radar_scores?.score_tier === "FLAGSHIP_VERIFIED" || Number(p.deep_scraped || 0) === 1;
      const tierModelTag = isFlagshipTier
        ? `<span style="display:inline-block;margin-top:4px;font-size:10px;padding:1px 5px;border-radius:4px;background:#ecfdf5;color:#059669;border:1px solid #a7f3d0;font-weight:700;">👑 旗舰实测</span>`
        : `<span style="display:inline-block;margin-top:4px;font-size:10px;padding:1px 5px;border-radius:4px;background:#f8fafc;color:#64748b;border:1px solid #e2e8f0;font-weight:600;">📊 标准建模</span>`;

      return `
        <tr>
          <td style="text-align:center;width:38px;">
            <input type="checkbox" class="product-select-chk" data-pid="${p.product_id}" onchange="toggleSelectProduct('${p.product_id}', this.checked)" ${STATE.selectedProductIds.has(p.product_id) ? "checked" : ""} />
          </td>
          <td>
            <div class="score-pill ${scoreClass}">${p.potential_score} 分</div>
            <div style="font-size:11px;color:var(--text-secondary);margin-top:4px;font-weight:600;">${p.tier}</div>
            ${tierModelTag}
          </td>
          <td style="max-width:320px;">
            <div class="prod-cell-wrap">
              ${getProductThumbHtml(p, 52)}
              <div>
                <div style="font-weight:700;font-size:13px;margin-bottom:2px;">${p.title_cn || p.title}</div>
                <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">${p.title_es || ""}</div>
                <span class="tag-chip" style="background:#eef6ff;color:#1677ff;">${normalizeMainCategory(p)} · ${getSubCategory(p)}</span>
              </div>
            </div>
          </td>
          <td>
            <div style="font-weight:800;font-size:14px;color:var(--fm-pink);">$${p.price_mxn} MXN</div>
            <div style="font-size:11.5px;color:var(--text-secondary);margin-top:2px;">📅 上架: ${p.release_date || "--"} (${p.days_online}天)</div>
          </td>
          <td>
            <div style="font-weight:700;">${p.sales_7d} 单 <span style="color:#059669;font-size:11.5px;">(+${p.growth_rate_7d}%)</span></div>
            <div style="font-size:11px;color:var(--text-muted);">总销: ${p.total_sales} 单 | ${p.gmv_3d_text || ""}</div>
          </td>
          <td>
            ${renderSparklineSVG(p.daily_sales_series, p.is_big_brand)}
          </td>
          <td>
            <div style="font-size:12px;font-weight:600;cursor:pointer;color:#1677ff;" onclick="filterByShopName('${(p.shop_name || "").replace(/'/g, "\\'")}')">🏪 ${p.shop_name} 🔍</div>
            <div style="font-size:11px;color:var(--text-muted);">店销: ${p.shop_total_sales || "--"} | 佣金 ${p.commission_rate_pct || 12}%</div>
          </td>
          <td>
            <div style="font-size:12px;">拿货: <strong>¥${p.cost_1688_rmb}</strong> (${p.weight_g}g)</div>
            <div style="font-size:11.5px;">✈️空运: <strong>${airM}%</strong> | 🚢海运: <strong style="color:#059669;">${seaM}%</strong></div>
          </td>
          <td>
            <div style="display:flex;flex-direction:column;gap:5px;">
              <div style="display:flex;gap:4px;">
                <button class="btn-sm primary" style="padding:2px 7px;font-size:11.5px;background:#161823;border-color:#161823;color:#fff;font-weight:700;" onclick="openProductDetailModal('${p.product_id}')" title="以专业电商商品网页形式查看全维数据">🛍️ 专业主页</button>
                <a class="btn-sm" href="${fmUrl}" target="_blank" style="text-decoration:none;text-align:center;">🔗 网页 ↗</a>
              </div>
              <div style="display:flex;gap:4px;">
                <button class="btn-sm" onclick="jumpToDueDiligence('${p.product_id}')">🎯 尽调</button>
                <button class="btn-sm" onclick="triggerSingleDeepDive('${p.product_id}')" title="穿透详情页补全高清大图与真实达人">🔬</button>
                <a class="btn-sm" href="${firstKwLink}" target="_blank" style="text-decoration:none;text-align:center;" title="按关键词直达 1688 货源">🏭 1688</a>
                <button class="btn-sm" onclick="search1688ByImage('${p.product_id}')" title="自动调用本地商品主图去 1688 以图搜图">🖼️</button>
                <button class="btn-sm" onclick="openRawJsonModal('${p.product_id}')">🗂️</button>
              </div>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

async function openProductDetailModal(productId) {
  let prod = STATE.products.find((p) => p.product_id === productId);
  if (!prod) return;

  const modal = document.getElementById("modal-product-detail");
  const container = document.getElementById("product-detail-modal-content");
  if (!modal || !container) return;

  modal.classList.add("open");

  // 1. 先用本地已有数据即时渲染骨架，保证零白屏秒开
  renderProductDetailHtml(prod, container);

  // 2. 异步向后端拉取全量详情（补齐详情页表格与真实达人/视频矩阵）
  try {
    const res = await fetch(`/api/product/raw?id=${encodeURIComponent(productId)}`);
    const data = await res.json();
    if (data && data.status === "ok" && data.product) {
      prod = { ...prod, ...data.product };
      renderProductDetailHtml(prod, container);
    }
  } catch (e) {
    console.warn("Detail fetch on-demand error:", e);
  }
}

function renderProductDetailHtml(p, container) {
  const pe = p.profit_eval || {};
  const air = pe.air_test_stage || {};
  const sea = pe.sea_scale_stage || {};
  const isFlagship = Boolean(p.deep_scraped || p.radar_scores?.score_tier === "FLAGSHIP_VERIFIED");
  const mainCat = normalizeMainCategory(p);
  const subCat = getSubCategory(p);
  const fmUrl = p.fastmoss_url || `https://www.fastmoss.com/zh/e-commerce/detail/${p.product_id}`;
  const firstKwLink = get1688SearchUrl(p);

  let creators = p.top_creators_json || [];
  if (typeof creators === "string") {
    try { creators = JSON.parse(creators); } catch (e) { creators = []; }
  }
  let videos = p.top_videos_json || [];
  if (typeof videos === "string") {
    try { videos = JSON.parse(videos); } catch (e) { videos = []; }
  }
  let skus = p.sku_specs_json || [];
  if (typeof skus === "string") {
    try { skus = JSON.parse(skus); } catch (e) { skus = []; }
  }
  let channel = p.channel_breakdown_json || {};
  if (typeof channel === "string") {
    try { channel = JSON.parse(channel); } catch (e) { channel = {}; }
  }
  const vPct = parseFloat(channel.video_pct || (p.creators_7d > 4 ? 68.0 : 54.0)).toFixed(1);
  const lPct = parseFloat(channel.live_pct || 18.0).toFixed(1);
  const cPct = parseFloat(channel.product_card_pct || p.product_card_share_pct || 14.0).toFixed(1);
  const oPct = Math.max(0, (100 - parseFloat(vPct) - parseFloat(lPct) - parseFloat(cPct))).toFixed(1);

  const dailySeries = Array.isArray(p.daily_sales_series) ? p.daily_sales_series : [];
  const seriesDays = dailySeries.length;
  const isRealDays = seriesDays >= 7;
  const maxDaySales = isRealDays ? Math.max(...dailySeries.map(s => (typeof s === "object" ? Number(s.sales || 0) : Number(s) || 0))) : 0;

  const compTags = Array.isArray(p.compliance_tags) ? p.compliance_tags : [];
  const primaryCompTag = compTags[0] || "✅ 墨西哥普货免NOM认证";
  const relDate = p.release_date || (p.days_online ? `近 ${p.days_online} 天上架` : "近期上架");
  const markupMul = p.cost_1688_rmb > 0 ? (p.price_mxn / 2.8 / p.cost_1688_rmb).toFixed(1) : "5.8";
  const displayImg = p.image_large_url || p.image_url || "";

  let creatorsHtml = "";
  if (Array.isArray(creators) && creators.length > 0) {
    creatorsHtml = `
      <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));gap:8px;margin-top:8px;">
        ${creators.map((c, i) => `
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;font-size:12px;display:flex;gap:10px;align-items:center;">
            ${c.avatar ? `<img src="${c.avatar}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;flex-shrink:0;background:#f1f5f9;" onerror="this.style.display='none'" />` : `<div style="width:34px;height:34px;border-radius:50%;background:#e0e7ff;color:#4338ca;display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0;">${(c.creator || '达')[0]}</div>`}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:700;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${c.creator || ''}">
                ${i + 1}. ${c.creator || '带货达人'}
              </div>
              <div style="color:#64748b;font-size:11px;margin-top:2px;">
                ${Array.isArray(c.metrics) && c.metrics.length ? c.metrics.join(' · ') : '关联带货热销'}
              </div>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  } else if (isFlagship) {
    creatorsHtml = `<div style="font-size:12px;color:#64748b;background:#f8fafc;padding:10px;border-radius:8px;">已抓取详情页达人概览（关联达人约 ${p.creators_7d || 6} 位），列表数据已沉淀入库。</div>`;
  } else {
    creatorsHtml = `
      <div style="background:#fff8fa;border:1px dashed #fecdd3;border-radius:8px;padding:10px 12px;font-size:12px;color:#9f1239;display:flex;justify-content:space-between;align-items:center;">
        <span>⚠️ 当前为榜单估算达人（约 ${p.creators_7d || 8} 位），点击右侧穿透详情页即可提取实测真实达人名单。</span>
        <button class="btn-sm" style="background:#eef2ff;color:#4f46e5;border-color:#c7d2fe;" onclick="triggerSingleDeepDive('${p.product_id}')">🔬 立即深潜穿透</button>
      </div>
    `;
  }

  let videosHtml = "";
  if (Array.isArray(videos) && videos.length > 0) {
    videosHtml = `
      <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));gap:8px;margin-top:8px;">
        ${videos.map((v, i) => `
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;font-size:12px;display:flex;gap:10px;align-items:center;">
            ${v.cover ? `<img src="${v.cover}" style="width:34px;height:46px;border-radius:4px;object-fit:cover;flex-shrink:0;background:#f1f5f9;" onerror="this.style.display='none'" />` : `<div style="width:34px;height:46px;border-radius:4px;background:#fef2f2;color:#dc2626;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;">🎬</div>`}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:700;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${v.video || ''}">
                ${i + 1}. ${v.video || '爆款短视频'}
              </div>
              <div style="color:#059669;font-size:11px;margin-top:2px;">
                ${Array.isArray(v.metrics) && v.metrics.length ? v.metrics.join(' · ') : '带货播放转化高'}
              </div>
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  let skusHtml = "";
  if (Array.isArray(skus) && skus.length > 0) {
    skusHtml = `
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;margin-top:14px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <div style="font-size:13px;font-weight:700;color:#0f172a;">📦 SKU 规格颗粒度出单矩阵 (共 ${skus.length} 款规格)</div>
          <div style="font-size:11.5px;color:#059669;font-weight:600;">已锁定实测热销款式与颜色</div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(180px, 1fr));gap:8px;">
          ${skus.slice(0, 8).map((sk, idx) => `
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;font-size:12px;">
              <div style="font-weight:700;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${sk.spec_name || ''}">
                🏷️ ${sk.spec_name || `规格 #${idx+1}`}
              </div>
              <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:4px;font-size:11.5px;">
                <span style="color:var(--fm-pink);font-weight:700;">$${sk.price_mxn || p.price_mxn} MXN</span>
                <span style="color:#64748b;">${sk.sales ? `出单: <strong>${sk.sales}</strong>` : '热销在售'}</span>
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  container.innerHTML = `
    <!-- 顶部电商面包屑导航与状态栏 -->
    <div style="background:#fff;border-bottom:1px solid #e2e8f0;padding:14px 22px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;position:sticky;top:0;z-index:20;">
      <div style="display:flex;align-items:center;gap:8px;font-size:12.5px;color:#64748b;flex-wrap:wrap;">
        <span style="cursor:pointer;" onclick="closeModals()">🏠 墨西哥选品中枢</span>
        <span>/</span>
        <span style="color:#0f172a;font-weight:600;">${mainCat}</span>
        <span>/</span>
        <span style="color:#0f172a;font-weight:600;">${subCat}</span>
        <span style="background:#f1f5f9;color:#475569;padding:2px 7px;border-radius:6px;font-size:11.5px;font-family:monospace;">ID: ${p.product_id}</span>
        ${
          isFlagship
            ? `<span style="background:#fef3c7;color:#b45309;padding:2px 8px;border-radius:20px;font-size:11.5px;font-weight:700;border:1px solid #fde68a;">👑 旗舰实测认证 (30天动销+渠道+达人+规格全维穿透)</span>`
            : `<span style="background:#f1f5f9;color:#64748b;padding:2px 8px;border-radius:20px;font-size:11.5px;font-weight:600;">📊 标准建模数据</span>`
        }
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <a href="${fmUrl}" target="_blank" class="btn-sm" style="text-decoration:none;padding:5px 12px;" title="在 FastMoss 查看该商品原网页">🔗 FastMoss 原网页 ↗</a>
        <button class="btn-sm" style="padding:5px 12px;font-weight:700;" onclick="closeModals()">✕ 关闭</button>
      </div>
    </div>

    <!-- 商品主体内容区：左图右文经典专业电商 PDP 布局 -->
    <div style="padding:22px;display:grid;grid-template-columns:370px 1fr;gap:26px;align-items:start;">
      <!-- 左列：高清商品大图展示橱窗与基本规格 -->
      <div>
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:14px;text-align:center;box-shadow:0 4px 12px rgba(15,23,42,0.04);position:relative;">
          ${
            displayImg && !displayImg.includes("/tt_shop/")
              ? `<img src="${displayImg}" style="width:100%;max-height:340px;object-fit:contain;border-radius:10px;background:#f8fafc;cursor:pointer;" onclick="window.open('${displayImg}', '_blank')" title="点击在新标签页查看实拍原图" alt="商品主图" />`
              : `<div style="height:280px;background:linear-gradient(135deg,#fff1f2,#ffe4e6);border-radius:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#e11d48;gap:8px;"><span style="font-size:54px;">📦</span><span style="font-weight:800;font-size:18px;">${subCat}</span><span style="font-size:12px;color:#9f1239;">（点击下方🔬深潜可抓取实拍大图）</span></div>`
          }
          <div style="position:absolute;top:22px;left:22px;background:rgba(15,23,42,0.82);color:#fff;font-size:11px;font-weight:700;padding:3px 8px;border-radius:6px;backdrop-filter:blur(4px);">
            ${p.source_board || "墨西哥热销"}
          </div>
          <div style="position:absolute;top:22px;right:22px;background:${p.image_large_url ? 'rgba(5,150,105,0.92)' : 'rgba(79,70,229,0.92)'};color:#fff;font-size:11px;font-weight:700;padding:3px 8px;border-radius:6px;backdrop-filter:blur(4px);">
            ${p.image_large_url ? '📷 540P 实拍原图' : '🖼️ 列表主图'}
          </div>
        </div>

        <!-- 墨西哥本土仓发货信任标 -->
        <div style="margin-top:12px;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:10px;padding:10px 14px;display:flex;align-items:center;gap:10px;color:#065f46;font-size:12.5px;font-weight:600;">
          <span style="font-size:18px;">🇲🇽</span>
          <div>
            <div>Envío rápido desde México (2-3 días)</div>
            <div style="font-size:11px;color:#047857;font-weight:400;">墨西哥海外仓本土一件代发 · 普货免NOM强认证</div>
          </div>
        </div>

        <!-- 核心定价体系与中墨采销倍率 -->
        <div style="margin-top:12px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;">
          <div style="font-size:12px;color:#64748b;font-weight:600;margin-bottom:6px;">💰 价格与利润模型</div>
          <div style="display:flex;align-items:baseline;gap:8px;">
            <span style="font-size:26px;font-weight:900;color:var(--fm-pink);">$${p.price_mxn}</span>
            <span style="font-size:13px;font-weight:700;color:#64748b;">MXN</span>
            <span style="font-size:12px;color:#059669;background:#ecfdf5;padding:2px 6px;border-radius:4px;font-weight:700;">≈ ¥${(p.price_mxn / 2.8).toFixed(1)} RMB</span>
          </div>
          <div style="margin-top:10px;padding-top:10px;border-top:1px dashed #e2e8f0;display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;">
            <div>1688 源头采购: <strong style="color:#0f172a;">¥${p.cost_1688_rmb}</strong></div>
            <div>中墨采销倍率: <strong style="color:#d97706;">${markupMul}x</strong></div>
            <div>单件预估克重: <strong style="color:#0f172a;">${p.weight_g || 260}g</strong></div>
            <div>带货佣金率: <strong style="color:#0f172a;">${p.commission_rate_pct || 12}%</strong></div>
          </div>
        </div>

        <!-- 所属店铺与上架档案 -->
        <div style="margin-top:12px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;font-size:12px;">
          <div style="font-size:12px;color:#64748b;font-weight:600;margin-bottom:8px;">🏪 店铺与上架档案</div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="color:#64748b;">所属店铺:</span>
            <span style="font-weight:700;color:#1677ff;cursor:pointer;" onclick="filterByShopName('${(p.shop_name || '').replace(/'/g, "\\'")}')">${p.shop_name} 🔍</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="color:#64748b;">店铺总销量:</span>
            <span style="font-weight:600;color:#0f172a;">${p.shop_total_sales || '热销本土店'}</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="color:#64748b;">首发上架:</span>
            <span style="font-weight:600;color:#0f172a;">📅 ${relDate}</span>
          </div>
          <div style="display:flex;justify-content:space-between;">
            <span style="color:#64748b;">合规风险评估:</span>
            <span style="font-weight:700;color:#059669;">${primaryCompTag}</span>
          </div>
        </div>
      </div>

      <!-- 右列：专业选品数据看板、动销趋势与实测穿透详情 -->
      <div>
        <!-- 标题区 -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:18px 20px;box-shadow:0 4px 12px rgba(15,23,42,0.04);">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span class="score-pill ${p.potential_score >= 80 ? 'score-s' : p.potential_score < 58 ? 'score-c' : 'score-a'}" style="font-size:13px;padding:3px 10px;">
              ${p.potential_score} 分 · ${p.tier}
            </span>
            <span style="font-size:12px;color:#64748b;font-weight:600;">FastMoss 墨西哥跨境五维蓝海评分</span>
          </div>
          <h1 style="font-size:20px;font-weight:800;color:#0f172a;line-height:1.4;margin-bottom:6px;">
            ${p.title_cn || p.title}
          </h1>
          <div style="font-size:13px;color:#64748b;line-height:1.5;">
            🇲🇽 ES 原标题: ${p.title_es || p.title}
          </div>
        </div>

        <!-- 动销指标三联看板 -->
        <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:12px;margin-top:14px;">
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:12px;color:#64748b;font-weight:600;">近 7 天销量 / 增速</div>
            <div style="font-size:22px;font-weight:800;color:#0f172a;margin-top:4px;">${p.sales_7d} <span style="font-size:12px;font-weight:600;">单</span></div>
            <div style="font-size:12px;color:#059669;font-weight:700;margin-top:2px;">+${p.growth_rate_7d}% 环比</div>
          </div>
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:12px;color:#64748b;font-weight:600;">近 3 天出单 / 销售额</div>
            <div style="font-size:22px;font-weight:800;color:var(--fm-pink);margin-top:4px;">${p.sales_3d || p.sales_7d} <span style="font-size:12px;font-weight:600;">单</span></div>
            <div style="font-size:12px;color:#64748b;margin-top:2px;">${p.gmv_3d_text || 'MX$' + Math.round(p.price_mxn * p.sales_7d).toLocaleString()}</div>
          </div>
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:12px;color:#64748b;font-weight:600;">历史总销量 / 总GMV</div>
            <div style="font-size:22px;font-weight:800;color:#1677ff;margin-top:4px;">${p.total_sales} <span style="font-size:12px;font-weight:600;">单</span></div>
            <div style="font-size:12px;color:#64748b;margin-top:2px;">${p.total_gmv_text || 'MX$' + Math.round(p.price_mxn * p.total_sales).toLocaleString()}</div>
          </div>
        </div>

        <!-- 📡 TikTok 渠道出单结构条 -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;margin-top:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="font-size:13px;font-weight:700;color:#0f172a;">📡 TikTok 墨西哥出单渠道分布结构</div>
            <div style="font-size:11.5px;color:#64748b;">${isFlagship ? '👑 详情页实测 API 渠道解析' : '📊 算法建模分布'}</div>
          </div>
          <div style="height:10px;width:100%;background:#f1f5f9;border-radius:6px;overflow:hidden;display:flex;">
            <div style="width:${vPct}%;background:#ec4899;" title="短视频出单 ${vPct}%"></div>
            <div style="width:${lPct}%;background:#f59e0b;" title="直播出单 ${lPct}%"></div>
            <div style="width:${cPct}%;background:#10b981;" title="商品卡/自然流出单 ${cPct}%"></div>
            ${oPct > 0 ? `<div style="width:${oPct}%;background:#64748b;" title="其他/橱窗 ${oPct}%"></div>` : ''}
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:12px;flex-wrap:wrap;gap:8px;">
            <div style="display:flex;align-items:center;gap:5px;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ec4899;"></span>
              <span>🎬 短视频带货: <strong style="color:#0f172a;">${vPct}%</strong></span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f59e0b;"></span>
              <span>📡 直播带货: <strong style="color:#0f172a;">${lPct}%</strong></span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;"></span>
              <span>🛒 商品卡自然流: <strong style="color:#0f172a;">${cPct}%</strong></span>
            </div>
          </div>
        </div>

        <!-- 逐日动销演变走势 -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 18px;margin-top:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
          <div>
            <div style="font-size:13px;font-weight:700;color:#0f172a;">
              📊 ${isRealDays ? `近 ${seriesDays} 天真实逐日出单动销演变走势` : '7 日逐日出单动销演变曲线'}
            </div>
            <div style="font-size:11.5px;color:#64748b;margin-top:2px;">
              ${isRealDays ? `波峰单日出单 ${maxDaySales} 单 · 详情页底层序列已完整解构` : '基于详情页真实 API 与列表 SVG 真实纵坐标解构'}
            </div>
          </div>
          <div>${renderSparklineSVG(dailySeries, p.is_big_brand)}</div>
        </div>

        <!-- 空运测款 vs 海运囤货 双阶段财务精算看板 -->
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-top:14px;">
          <div style="font-size:13.5px;font-weight:700;color:#0f172a;margin-bottom:10px;">🧮 墨西哥本土海外仓囤货 · 财务模型测算</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;">
              <div style="font-weight:700;color:#1677ff;font-size:13px;margin-bottom:6px;">✈️ 阶段一：空运快速测款 (100件)</div>
              <div style="font-size:12px;color:#475569;line-height:1.7;">
                <div>• 单件净利: <strong style="color:${(air.net_profit_rmb || 0) >= 0 ? '#059669' : '#dc2626'}">¥${air.net_profit_rmb || '--'} RMB</strong> (${air.margin_pct || '--'}%)</div>
                <div>• 100件测款启动压款: <strong>¥${air.upfront_capital_rmb || '--'} RMB</strong></div>
              </div>
            </div>
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:12px;">
              <div style="font-weight:700;color:#059669;font-size:13px;margin-bottom:6px;">🚢 阶段二：海运放大囤货 (500件)</div>
              <div style="font-size:12px;color:#166534;line-height:1.7;">
                <div>• 单件净利: <strong style="color:#059669;font-size:14px;">¥${sea.net_profit_rmb || '--'} RMB</strong> (${sea.margin_pct || '--'}%)</div>
                <div>• 投流保本 ROI (Break-even): <strong>${sea.breakeven_roi || '--'}</strong></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 📦 SKU 规格颗粒度出单矩阵 -->
        ${skusHtml}

        <!-- 👑 深度穿透核心专区：真实达人矩阵与爆款视频 -->
        <div style="background:#fff;border:1.5px solid ${isFlagship ? '#fed7aa' : '#e2e8f0'};border-radius:12px;padding:16px;margin-top:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div style="display:flex;align-items:center;gap:6px;">
              <span style="font-size:16px;">👑</span>
              <span style="font-weight:800;font-size:14px;color:#0f172a;">详情页实测矩阵 · 带货达人与关联视频</span>
            </div>
            <div style="font-size:12px;color:#64748b;">
              关联达人: <strong>${p.creators_7d || 0}</strong> 位 · 关联视频: <strong>${p.videos_7d || 0}</strong> 条
            </div>
          </div>

          <div style="margin-top:10px;">
            <div style="font-size:12px;font-weight:700;color:#475569;margin-bottom:4px;">👥 核心带货达人 (Top Creators):</div>
            ${creatorsHtml}
          </div>

          ${
            videosHtml
              ? `<div style="margin-top:12px;">
                  <div style="font-size:12px;font-weight:700;color:#475569;margin-bottom:4px;">🎬 核心带货视频 (Top Videos):</div>
                  ${videosHtml}
                </div>`
              : ""
          }
        </div>

        <!-- 底部一键直达专业动作工具条 -->
        <div style="margin-top:18px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;background:#fff;padding:12px;border:1px solid #e2e8f0;border-radius:12px;">
          <button class="btn-sm primary" style="background:#4f46e5;border-color:#4f46e5;font-weight:700;" onclick="triggerSingleDeepDive('${p.product_id}')">
            🔬 重新穿透深潜
          </button>
          <button class="btn-sm" style="font-weight:700;" onclick="closeModals();jumpToDueDiligence('${p.product_id}')">
            🎯 @智能体立项尽调
          </button>
          <a href="${firstKwLink}" target="_blank" class="btn-sm" style="text-decoration:none;font-weight:700;" title="使用源头工厂关键词直达 1688 搜索">
            🏭 1688 搜同款货源
          </a>
          <button class="btn-sm" style="font-weight:700;color:#0284c7;border-color:#bae6fd;background:#f0f9ff;" onclick="search1688ByImage('${p.product_id}')" title="自动调用本地对应商品保存的主图去 1688 进行以图搜款">
            🖼️ 主图搜 1688
          </button>
          <button class="btn-sm" onclick="closeModals();jumpToCalc('${p.product_id}')">
            🧮 载入利润测算台
          </button>
          <button class="btn-sm" onclick="closeModals();openToolbox('voc_insight', '${p.product_id}')">
            ✨ AI 工具箱处理
          </button>
          <button class="btn-sm" onclick="openRawJsonModal('${p.product_id}')" title="查看底层全量原始快照">
            🗂️ 原始 JSON
          </button>
        </div>
      </div>
    </div>
  `;
}

async function openRawJsonModal(productId) {
  const prod = STATE.products.find((p) => p.product_id === productId);
  if (!prod) return;
  document.getElementById("raw-json-modal-title").textContent = `🗂️ 旗舰全量网页数据存档 · ${prod.title_cn || prod.title}`;
  document.getElementById("raw-json-modal-body").textContent = "⏳ 正在按需拉取本地 SQLite 原始快照...";
  document.getElementById("modal-raw-json").classList.add("open");

  let rawSnapshot = prod.raw_payload_json || {};
  try {
    const res = await fetch(`/api/product/raw?id=${encodeURIComponent(productId)}`);
    const data = await res.json();
    if (data && data.status === "ok" && data.raw_payload_json) {
      rawSnapshot = data.raw_payload_json;
    }
  } catch (e) {
    console.warn("Failed to load on-demand raw payload:", e);
  }

  const fullArchive = {
    product_id: prod.product_id,
    fastmoss_url: prod.fastmoss_url,
    title_cn: prod.title_cn,
    title_es: prod.title_es,
    keywords_1688: prod.keywords_1688,
    release_date: prod.release_date,
    days_online: prod.days_online,
    price_mxn: prod.price_mxn,
    sales_3d: prod.sales_3d,
    sales_7d: prod.sales_7d,
    total_sales: prod.total_sales,
    gmv_3d_text: prod.gmv_3d_text,
    total_gmv_text: prod.total_gmv_text,
    shop_name: prod.shop_name,
    shop_total_sales: prod.shop_total_sales,
    shop_url: prod.shop_url,
    commission_rate_pct: prod.commission_rate_pct,
    weight_g: prod.weight_g,
    cost_1688_rmb: prod.cost_1688_rmb,
    potential_score: prod.potential_score,
    score_tier: prod.radar_scores?.score_tier || (prod.deep_scraped ? "FLAGSHIP_VERIFIED" : "STANDARD_ADAPTIVE"),
    radar_scores: prod.radar_scores,
    snapshot_count: prod.snapshot_count,
    delta_sales: prod.delta_sales,
    deep_scraped: prod.deep_scraped,
    raw_webpage_snapshot: rawSnapshot,
  };
  document.getElementById("raw-json-modal-body").textContent = JSON.stringify(fullArchive, null, 2);
}

function showToast(msg, type = "info") {
  let box = document.getElementById("global-toast-container");
  if (!box) {
    box = document.createElement("div");
    box.id = "global-toast-container";
    box.style.cssText =
      "position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;";
    document.body.appendChild(box);
  }
  const toast = document.createElement("div");
  toast.style.cssText =
    "background:rgba(15,23,42,0.92);color:#fff;padding:10px 18px;border-radius:10px;font-size:13.5px;font-weight:600;box-shadow:0 8px 24px rgba(0,0,0,0.18);backdrop-filter:blur(8px);transition:all 0.3s ease;opacity:0;transform:translateY(-8px);pointer-events:auto;";
  toast.textContent = msg;
  box.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  });
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-8px)";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

async function triggerSingleDeepDive(productId) {
  if (!productId) return;
  const cleanPid = String(productId).trim();
  showToast(`🔬 正在启动单品详情页深潜 (${cleanPid})...`);
  renderLiveScrapeProgress({
    is_running: true,
    progress_pct: 15,
    message: `🔬 正在深潜穿透单品 (${cleanPid}) 详情页，提取实拍主图、达人与视频矩阵...`,
  });
  try {
    const res = await fetch("/api/scraper/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "deep_batch",
        target: cleanPid,
      }),
    });
    const data = await res.json();
    if (data.status === "ok") {
      showToast(data.message || "已唤醒 Chrome 执行单品详情页深潜！");
      startPollingLiveScrape();
    } else if (data.status === "blocked") {
      alert(data.message);
      renderLiveScrapeProgress({ is_running: false, progress_pct: 100, message: "⛔ " + data.message.split("\n")[0] });
    } else {
      showToast("启动深潜失败: " + (data.message || "未知错误"));
    }
  } catch (e) {
    showToast("启动深潜失败: " + e.message);
  }
}

async function triggerBatchDeepDive() {
  const capSelect = document.getElementById("deep-dive-capacity");
  const capacity = capSelect ? parseInt(capSelect.value, 10) : 20;

  // 1. 获取库内所有未深潜穿透的商品（排除 DEMO 演示数据）
  let unscraped = STATE.products.filter(
    (p) => !String(p.product_id).startsWith("MX_DEMO") && !p.deep_scraped
  );

  // 2. 严格按评分从高往低排序；评分相同时按近7天销量从大到小排序
  unscraped.sort((a, b) => {
    const diffScore = (Number(b.potential_score) || 0) - (Number(a.potential_score) || 0);
    if (Math.abs(diffScore) > 0.01) return diffScore;
    return (Number(b.sales_7d) || 0) - (Number(a.sales_7d) || 0);
  });

  let candidates = unscraped;

  // 3. 若全库所有商品均已完成深潜，提示用户并提供按评分重巡刷新选项
  if (candidates.length === 0) {
    if (!confirm("🎉 恭喜！当前库内商品已全部完成详情页深潜穿透。是否对全库评分从高到低的前 " + capacity + " 款商品重新巡检刷新？")) {
      return;
    }
    candidates = STATE.products
      .filter((p) => !String(p.product_id).startsWith("MX_DEMO"))
      .sort((a, b) => {
        const diffScore = (Number(b.potential_score) || 0) - (Number(a.potential_score) || 0);
        if (Math.abs(diffScore) > 0.01) return diffScore;
        return (Number(b.sales_7d) || 0) - (Number(a.sales_7d) || 0);
      });
  }

  const targetProducts = candidates.slice(0, capacity);
  const pidList = targetProducts.map((p) => p.product_id).filter(Boolean);

  if (pidList.length === 0) {
    showToast("⚠️ 未找到有效的商品ID进行深潜！");
    return;
  }

  const highestScore = targetProducts[0]?.potential_score || 0;
  const lowestScore = targetProducts[targetProducts.length - 1]?.potential_score || 0;

  showToast(`🔬 已按评分从高到低锁定 ${pidList.length} 款未穿透商品（最高 ${highestScore}分 ➔ 最低 ${lowestScore}分），启动超长静默深潜巡航...`);
  renderLiveScrapeProgress({
    is_running: true,
    progress_pct: 5,
    message: `🔬 正在按评分从高到低为 ${pidList.length} 款商品启动静默微巡航深潜 (8~15秒随机低频防风控)...`,
  });

  try {
    const res = await fetch("/api/scraper/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "deep_batch",
        target: pidList.join(","),
      }),
    });
    const data = await res.json();
    if (data.status === "ok") {
      showToast(data.message || `🚀 已成功下发 ${pidList.length} 款商品静默深潜队列！`);
      startPollingLiveScrape();
    } else if (data.status === "blocked") {
      alert(data.message);
      renderLiveScrapeProgress({ is_running: false, progress_pct: 100, message: "⛔ " + data.message.split("\n")[0] });
    } else {
      showToast("批量深潜启动失败: " + (data.message || "未知错误"));
    }
  } catch (e) {
    showToast("批量深潜启动失败: " + e.message);
  }
}

function jumpToDueDiligence(productId) {
  document.getElementById("agent-product-selector").value = productId;
  runAgentWorkflow("product_due_diligence", productId);
}

function jumpToCalc(productId) {
  switchView("assets");
  document.getElementById("calc-product-select").value = productId;
  onSelectCalcProduct();
}

function onSelectCalcProduct() {
  const pid = document.getElementById("calc-product-select").value;
  const prod = STATE.products.find((p) => p.product_id === pid) || STATE.products[0];
  if (!prod) return;

  document.getElementById("calc-price-mxn").value = prod.price_mxn;
  document.getElementById("calc-cost-rmb").value = prod.cost_1688_rmb;
  document.getElementById("calc-weight-g").value = prod.weight_g;
  document.getElementById("calc-kanban-stage").value = prod.kanban_stage || "candidate";
  document.getElementById("calc-supplier-url").value = prod.supplier_1688_url || "";
  document.getElementById("calc-kanban-notes").value = prod.kanban_notes || "";

  const linksBox = document.getElementById("calc-1688-links");
  let kws = (prod.links_1688 && prod.links_1688.keyword_links) || [];
  if (kws.length === 0 && prod.keywords_1688 && prod.keywords_1688.length > 0) {
    kws = prod.keywords_1688.map((kw) => ({
      keyword: kw,
      url: `https://s.1688.com/selloffer/offer_search.htm?keywords=${encodeURIComponent(kw)}&_input_charset=utf-8&n=y`,
    }));
  }
  let linksHtml = kws
    .map(
      (k) =>
        `<a href="${k.url}" target="_blank" class="btn-sm" style="text-decoration:none;color:var(--fm-pink);border-color:var(--fm-pink-border);background:var(--fm-pink-light);">🔍 搜 1688「${k.keyword}」↗</a>`
    )
    .join("");

  if (prod.image_url) {
    linksHtml += `<button onclick="search1688ByImage('${prod.product_id}')" class="btn-sm" style="margin-left:4px;color:#0284c7;border-color:#bae6fd;background:#f0f9ff;cursor:pointer;" title="自动调用本地商品主图去 1688 以图搜款">🖼️ 用主图搜 1688 ↗</button>`;
  }
  linksBox.innerHTML = linksHtml;

  runLiveProfitCalc();
}

async function runLiveProfitCalc() {
  const price_mxn = parseFloat(document.getElementById("calc-price-mxn").value) || 259;
  const cost_1688_rmb = parseFloat(document.getElementById("calc-cost-rmb").value) || 15;
  const weight_g = parseFloat(document.getElementById("calc-weight-g").value) || 250;

  try {
    const resp = await fetch("/api/profit/calc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ price_mxn, cost_1688_rmb, weight_g }),
    });
    const data = await resp.json();
    if (data.status !== "ok") return;
    const pf = data.profit;

    document.getElementById("calc-markup-badge").textContent = `中墨采销倍率: ${pf.markup_multiple}x (折合 ¥${pf.revenue_rmb})`;
    document.getElementById("calc-decision-banner").innerHTML = `<strong>${pf.decision}</strong>：${pf.decision_detail}`;

    const air = pf.air_test_stage;
    document.getElementById("calc-air-details").innerHTML = `
      <div>• 单件总成本(含拿货/空运/尾程/佣金)：<strong>¥${air.total_cost_rmb} RMB</strong></div>
      <div>• 空运测款单件净利：<strong style="color:${air.net_profit_rmb >= 0 ? "#059669" : "#dc2626"};">¥${air.net_profit_rmb} RMB (${air.net_profit_mxn} MXN)</strong></div>
      <div>• 空运期净利率：<strong>${air.margin_pct}%</strong></div>
      <div>• <strong>${air.batch_qty}件空运测款首批启动资金：¥${air.upfront_capital_rmb} RMB</strong></div>
    `;

    const sea = pf.sea_scale_stage;
    document.getElementById("calc-sea-details").innerHTML = `
      <div>• 单件总成本(含拿货/海运/尾程/佣金)：<strong>¥${sea.total_cost_rmb} RMB</strong></div>
      <div>• 海运囤货单件净利：<strong style="color:#059669;font-size:15px;">¥${sea.net_profit_rmb} RMB (${sea.net_profit_mxn} MXN)</strong></div>
      <div>• 海运稳定期净利率：<strong style="color:#059669;font-size:15px;">${sea.margin_pct}%</strong></div>
      <div>• 投流保本 ROI (Break-even ROAS)：<strong>${sea.breakeven_roi}</strong></div>
    `;

    const bd = pf.breakdown_rmb;
    document.getElementById("calc-cost-breakdown").innerHTML = `
      💡 <strong>单件成本拆解 (折合RMB)</strong>：1688拿货 <code>¥${bd.cost_1688}</code> | 空运头程 <code>¥${bd.air_shipping}</code> (海运仅 <code>¥${bd.sea_shipping}</code>) | 墨西哥海外仓一件代发尾程 <code>¥${bd.local_fulfillment}</code> | 平台佣金+支付费 <code>¥${bd.platform_fee}</code> | 达人佣金 <code>¥${bd.affiliate_commission}</code> | 退货战损预留 <code>¥${bd.return_ad_buffer}</code>
    `;
  } catch (e) {
    console.error(e);
  }
}

async function saveProductSourcing() {
  const product_id = document.getElementById("calc-product-select").value;
  const price_mxn = parseFloat(document.getElementById("calc-price-mxn").value) || 259;
  const cost_1688_rmb = parseFloat(document.getElementById("calc-cost-rmb").value) || 15;
  const weight_g = parseFloat(document.getElementById("calc-weight-g").value) || 250;
  const kanban_stage = document.getElementById("calc-kanban-stage").value;
  const supplier_1688_url = document.getElementById("calc-supplier-url").value;
  const kanban_notes = document.getElementById("calc-kanban-notes").value;

  await fetch("/api/product/update_sourcing", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id,
      price_mxn,
      cost_1688_rmb,
      weight_g,
      kanban_stage,
      supplier_1688_url,
      kanban_notes,
    }),
  });
  await loadDashboardData();
  alert("✅ 已保存 1688 核价并更新测款看板状态！");
}

function renderKanbanBoard() {
  const stages = [
    { key: "candidate", title: "📥 候选池" },
    { key: "due_diligence", title: "🔍 深度尽调中" },
    { key: "sourcing", title: "🏭 1688寻源核价" },
    { key: "testing", title: "✈️ 空运小批测款中" },
    { key: "rejected", title: "❌ 已淘汰/避坑样本" },
  ];

  const board = document.getElementById("kanban-board-container");
  board.innerHTML = stages
    .map((st) => {
      const items = STATE.products.filter((p) => (p.kanban_stage || "candidate") === st.key);
      const cardsHtml = items
        .map(
          (item) => `
          <div class="kanban-item">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;align-items:center;">
              <span class="score-pill ${item.potential_score >= 80 ? "score-s" : item.potential_score < 58 ? "score-c" : "score-a"}" style="font-size:10.5px;padding:2px 7px;">
                ${item.potential_score}分
              </span>
              <span style="font-weight:700;font-size:12px;">$${item.price_mxn} MXN</span>
            </div>
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:6px;">
              ${getProductThumbHtml(item, 40)}
              <div style="font-weight:700;font-size:12px;line-height:1.35;">${item.title_cn || item.title}</div>
            </div>
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
              1688: ¥${item.cost_1688_rmb} | 海运净利: <strong>${item.profit_eval?.sea_scale_stage?.margin_pct || "--"}%</strong>
            </div>
            ${item.kanban_notes ? `<div style="font-size:11px;background:#f7f8fb;padding:5px 7px;border-radius:6px;color:var(--text-secondary);margin-bottom:6px;">📝 ${item.kanban_notes}</div>` : ""}
            <div style="display:flex;justify-content:space-between;gap:4px;">
              <button class="btn-sm" style="font-size:11px;padding:3px 7px;" onclick="jumpToCalc('${item.product_id}')">编辑状态</button>
              <a class="btn-sm" style="font-size:11px;padding:3px 7px;text-decoration:none;" href="${item.fastmoss_url}" target="_blank">🔗网页</a>
              <button class="btn-sm" style="font-size:11px;padding:3px 7px;" onclick="jumpToDueDiligence('${item.product_id}')">尽调</button>
            </div>
          </div>
        `
        )
        .join("");

      return `
        <div class="kanban-col">
          <div class="kanban-col-head">
            <span>${st.title}</span>
            <span class="badge">${items.length}</span>
          </div>
          <div>${cardsHtml || `<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:18px 0;">暂无商品</div>`}</div>
        </div>
      `;
    })
    .join("");
}

function renderScrapeTasksTable() {
  const tbody = document.getElementById("scrape-tasks-body");
  if (!STATE.scrape_tasks.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);">暂无采集日志</td></tr>`;
    return;
  }
  tbody.innerHTML = STATE.scrape_tasks
    .map(
      (t) => `
      <tr>
        <td>${t.created_at}</td>
        <td><code>${t.task_type}</code></td>
        <td>${t.target_url_or_board}</td>
        <td><strong>${t.status}</strong></td>
        <td>${t.items_collected}</td>
        <td>${t.log_message}</td>
      </tr>
    `
    )
    .join("");
}

let SCRAPE_POLL_TIMER = null;

function renderLiveScrapeProgress(st) {
  const isRunning = Boolean(st && st.is_running);
  const pct = st && typeof st.progress_pct === "number" ? st.progress_pct : 0;
  const msg = (st && st.message) || "就绪";

  const stopTopBtn = document.getElementById("btn-stop-scrape-top");
  if (stopTopBtn) stopTopBtn.style.display = isRunning ? "inline-block" : "none";

  const bannerProd = document.getElementById("live-banner-products");
  if (bannerProd) {
    bannerProd.style.display = isRunning || pct === 100 ? "block" : "none";
    document.getElementById("live-msg-products").textContent = msg;
    document.getElementById("live-pct-products").textContent = `${pct}%`;
    document.getElementById("live-bar-products").style.width = `${Math.max(5, pct)}%`;
  }

  const bannerScraper = document.getElementById("live-banner-scraper");
  if (bannerScraper) {
    const dot = document.getElementById("live-dot-scraper");
    if (dot) dot.style.display = isRunning ? "inline-block" : "none";
    document.getElementById("live-msg-scraper").textContent = msg;
    document.getElementById("live-pct-scraper").textContent = isRunning ? `${pct}% 巡航中` : "已完成 / 就绪";
    document.getElementById("live-bar-scraper").style.width = `${Math.max(8, pct)}%`;
  }

  const btn = document.getElementById("btn-oneclick-scrape");
  if (btn) {
    btn.disabled = isRunning;
    btn.textContent = isRunning ? `⏳ 无人值守巡航抓数中 (${pct}%)...` : "🛳️ 开启「无人值守防风控自动连续抓数」";
  }

  const deepBar = document.getElementById("floating-deep-cruise-bar");
  const isDeepScraping = Boolean(st && (st.board === "详情页静默深潜" || String(st.message).includes("静默深潜")));
  if (deepBar) {
    if (isRunning && isDeepScraping) {
      deepBar.style.display = "block";
      document.getElementById("deep-cruise-title").textContent = "🔬 静默深潜微巡航 (低频防风控)";
      document.getElementById("deep-cruise-pct").textContent = `${pct}%`;
      document.getElementById("deep-cruise-msg").textContent = msg;
      document.getElementById("deep-cruise-actions").innerHTML = `
        <button class="btn-sm" style="padding: 2px 8px; font-size: 11px; background:#fef2f2; color:#dc2626; border-color:#fecdd3;" onclick="stopPlaywrightScrape()">⏸️ 暂停/停止</button>
      `;
    } else if (!isRunning) {
      checkDeepCheckpointUI();
    }
  }
}

function startPollingLiveScrape() {
  if (SCRAPE_POLL_TIMER) clearInterval(SCRAPE_POLL_TIMER);
  SCRAPE_POLL_TIMER = setInterval(async () => {
    try {
      const resp = await fetch("/api/scraper/status");
      const st = await resp.json();
      renderLiveScrapeProgress(st);
      await loadDashboardData();
      if (!st.is_running) {
        clearInterval(SCRAPE_POLL_TIMER);
        SCRAPE_POLL_TIMER = null;
        refreshCheckpointUI();
      }
    } catch (e) {}
  }, 1500);
}

function syncBoardCheckboxes(el) {
  const b = el?.dataset?.board;
  if (!b) return;
  document.querySelectorAll(`.sync-board-chk[data-board="${b}"]`).forEach((chk) => {
    chk.checked = el.checked;
  });
  updateSearchRangeBox();
}

function updateSearchRangeBox() {
  const on = !!document.querySelector('.sync-board-chk[data-board="search"]')?.checked;
  const box = document.getElementById("search-range-box");
  if (box) box.style.display = on ? "inline-flex" : "none";
  if (on) {
    const curStart = document.getElementById("top-scrape-start-page")?.value || "1";
    const curPages = document.getElementById("top-scrape-pages-select")?.value || "200";
    const sStart = document.getElementById("search-start-page");
    const sMax = document.getElementById("search-max-pages");
    if (sStart && (!sStart.value || sStart.value === "1")) sStart.value = curStart;
    if (sMax && (!sMax.value || sMax.value === "500")) sMax.value = curPages;
  }
}

function syncTopCategorySelect(sel) {
  const val = sel?.value || "";
  document.querySelectorAll(".chk-scrape-cat").forEach((chk) => {
    chk.checked = Boolean(val && chk.value === val);
  });
}

function syncStartPageInput(el) {
  const val = el?.value || "1";
  const a = document.getElementById("top-scrape-start-page");
  const b = document.getElementById("scraper-start-page");
  const s = document.getElementById("search-start-page");
  if (a && a !== el) a.value = val;
  if (b && b !== el) b.value = val;
  if (s && s !== el) s.value = val;
}

function syncSearchStartPageInput(el) {
  syncStartPageInput(el);
}

function syncSearchMaxPagesInput(el) {
  const val = el?.value || "500";
  const a = document.getElementById("top-scrape-pages-select");
  const b = document.getElementById("scraper-pages-select");
  if (a) {
    for (const opt of a.options) {
      if (opt.value === String(val)) {
        a.value = val;
        break;
      }
    }
  }
  if (b) {
    for (const opt of b.options) {
      if (opt.value === String(val)) {
        b.value = val;
        break;
      }
    }
  }
}

function syncPagesSelect(sel) {
  const val = sel?.value || "5";
  const a = document.getElementById("top-scrape-pages-select");
  const b = document.getElementById("scraper-pages-select");
  const sm = document.getElementById("search-max-pages");
  if (a && a !== sel) a.value = val;
  if (b && b !== sel) b.value = val;
  if (sm) sm.value = val;
}

// FastMoss 墨西哥站 TikTok Shop 一级类目（与 FastMoss 榜单页「商品分类」筛选文案保持一致）
const SCRAPE_CATEGORIES = [
  "女装与女士内衣",
  "男装与男士内衣",
  "美妆个护",
  "手机与数码",
  "电脑办公",
  "家电",
  "家居用品",
  "厨房用品",
  "家纺布艺",
  "家装建材",
  "五金工具",
  "运动与户外",
  "玩具和爱好",
  "母婴用品",
  "儿童时尚",
  "宠物用品",
  "时尚配件",
  "鞋靴",
  "箱包",
  "汽车与摩托车",
  "保健",
  "食品饮料",
];

function renderScrapeCategoryChips() {
  const box = document.getElementById("scrape-cat-chips");
  if (!box || box.dataset.ready) return;
  box.innerHTML = SCRAPE_CATEGORIES.map(
    (c) =>
      `<label style="display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" class="chk-scrape-cat" value="${c}" /> ${c}</label>`
  ).join("");
  box.dataset.ready = "1";
}

function toggleAllScrapeCats(on) {
  document.querySelectorAll(".chk-scrape-cat").forEach((el) => (el.checked = on));
}

async function refreshCheckpointUI() {
  try {
    const ck = await (await fetch("/api/scraper/checkpoint")).json();
    const box = document.getElementById("resume-checkpoint-box");
    const topBtn = document.getElementById("btn-resume-top");
    const topPill = document.getElementById("top-checkpoint-pill");
    const topPillLbl = document.getElementById("top-checkpoint-label");
    const show = !!ck.has_checkpoint;
    if (box) {
      box.style.display = show ? "block" : "none";
      if (show) {
        document.getElementById("resume-checkpoint-text").innerHTML =
          `📌 发现上次未完成的抓取进度：<strong>${ck.board_label || ""}</strong> 第 <strong>${ck.next_page}</strong> 页起` +
          `（组合 ${ck.task_idx + 1}/${ck.task_total}，已累计入库 ${ck.collected} 款，保存于 ${ck.updated_at}）`;
      }
    }
    if (topBtn) {
      topBtn.style.display = show ? "inline-block" : "none";
      if (show) {
        topBtn.textContent = `⏯ 恢复上次进度 (${ck.board_label || "续抓"}·第${ck.next_page}页)`;
      }
    }
    if (topPill) {
      topPill.style.display = show ? "flex" : "none";
      if (show && topPillLbl) {
        topPillLbl.innerHTML = `📌 断点：<strong>${ck.board_label || ""} · 第 ${ck.next_page} 页</strong> (已入库 ${ck.collected} 款)`;
      }
    }
  } catch (e) {}
}

async function checkDeepCheckpointUI() {
  try {
    const res = await fetch("/api/scraper/deep_checkpoint");
    const d = await res.json();
    const deepBar = document.getElementById("floating-deep-cruise-bar");
    if (!deepBar) return;
    if (d && d.has_checkpoint && d.pending_count > 0) {
      deepBar.style.display = "block";
      document.getElementById("deep-cruise-title").textContent = "⏸️ 批量深潜有未完成断点";
      document.getElementById("deep-cruise-pct").textContent = `剩余 ${d.pending_count} 款`;
      document.getElementById("deep-cruise-msg").textContent = `上次已完成 ${d.done_count}/${d.total} 款，当前处于暂停状态 (${d.updated_at})`;
      document.getElementById("deep-cruise-actions").innerHTML = `
        <button class="btn-sm primary" style="padding: 3px 10px; font-size: 11.5px; background:#4f46e5; border-color:#4f46e5; font-weight:700;" onclick="resumeDeepDiveScrape()">▶️ 断点继续 (${d.pending_count}款)</button>
        <button class="btn-sm" style="padding: 3px 8px; font-size: 11px;" onclick="clearDeepCheckpointUI()">✕ 放弃</button>
      `;
    } else if (!SCRAPE_POLL_TIMER) {
      deepBar.style.display = "none";
    }
  } catch (e) {}
}

async function resumeDeepDiveScrape() {
  try {
    const res = await fetch("/api/scraper/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "deep_batch",
        resume: true,
      }),
    });
    const data = await res.json();
    if (data.status === "ok") {
      showToast("🚀 已从断点恢复静默深潜！");
      startPollingLiveScrape();
    } else {
      showToast("恢复深潜失败: " + data.message);
    }
  } catch (e) {
    showToast("恢复深潜失败: " + e.message);
  }
}

async function clearDeepCheckpointUI() {
  if (!confirm("确定清除当前未完成的深潜断点记录？")) return;
  await fetch("/api/scraper/deep_checkpoint/clear", { method: "POST" });
  const deepBar = document.getElementById("floating-deep-cruise-bar");
  if (deepBar) deepBar.style.display = "none";
  showToast("已清除深潜断点");
}

async function postTrigger(body) {
  const res = await fetch("/api/scraper/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (data.status === "blocked") {
    alert(data.message);
    renderLiveScrapeProgress({ is_running: false, progress_pct: 100, message: "⛔ " + data.message.split("\n")[0] });
    return false;
  }
  return true;
}

async function resumePlaywrightScrape() {
  renderLiveScrapeProgress({ is_running: true, progress_pct: 6, message: "⏯ 正在恢复上次抓取进度..." });
  if (await postTrigger({ mode: "cruise", boards: "new", pages: 1, resume: true })) startPollingLiveScrape();
}

async function applyScraperSettings() {
  const boardOrder = ["soaring", "hot", "new", "search"];
  const selectedBoards = boardOrder.filter((b) => {
    const el = document.querySelector(`.sync-board-chk[data-board="${b}"]`);
    return el && el.checked;
  });
  const boards = selectedBoards.length ? selectedBoards.join(",") : "search";

  let categories = Array.from(document.querySelectorAll(".chk-scrape-cat:checked"))
    .map((el) => el.value)
    .join(",");
  if (!categories) {
    const topCat = document.getElementById("top-scrape-cat-select")?.value || "";
    if (topCat) categories = topCat;
  }

  const clampPg = (v, d) => Math.min(500, Math.max(1, parseInt(v, 10) || d));
  const pages = clampPg(
    document.getElementById("top-scrape-pages-select")?.value ||
      document.getElementById("scraper-pages-select")?.value ||
      "500",
    500
  );
  const startPage = clampPg(
    document.getElementById("top-scrape-start-page")?.value ||
      document.getElementById("scraper-start-page")?.value ||
      "1",
    1
  );

  const searchPagesVal = clampPg(document.getElementById("search-max-pages")?.value || pages, 500);
  const searchStartVal = clampPg(document.getElementById("search-start-page")?.value || startPage, 1);

  const isSearchSelected = selectedBoards.includes("search");
  const effectiveStartPage = (isSearchSelected && selectedBoards.length === 1) ? searchStartVal : startPage;
  const effectivePages = (isSearchSelected && selectedBoards.length === 1) ? searchPagesVal : pages;

  try {
    const res = await fetch("/api/scraper/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        boards,
        categories,
        start_page: effectiveStartPage,
        pages: effectivePages,
        search_start: searchStartVal,
        search_pages: searchPagesVal,
      }),
    });
    const data = await res.json();
    if (data.status === "ok") {
      const badge = document.getElementById("settings-locked-badge");
      if (badge) {
        badge.style.display = "inline-flex";
        badge.innerHTML = `✅ 已锁定：第 ${effectiveStartPage} 页起抓到 ${effectivePages} 页`;
      }
      const topPill = document.getElementById("top-checkpoint-pill");
      if (topPill) topPill.style.display = "none";
      const resumeBox = document.getElementById("resume-checkpoint-box");
      if (resumeBox) resumeBox.style.display = "none";
      const resumeTopBtn = document.getElementById("btn-resume-top");
      if (resumeTopBtn) resumeTopBtn.style.display = "none";

      alert(`✅ 设定已实打实锁定并同步到后端！\n\n🎯 设定抓取范围：${boards}\n📍 设定起始页：第 ${effectiveStartPage} 页\n📊 设定翻页上限：${effectivePages} 页\n\n旧断点已自动彻底清空。现在请直接点击「🛳️ 开启无人值守连续抓数」开始抓取！`);
    } else {
      alert("❌ 锁定失败: " + (data.message || "未知错误"));
    }
  } catch (err) {
    alert("❌ 无法连接到中枢后台: " + err);
  }
}

async function discardCheckpoint() {
  if (!confirm("确定清除上次断点？清除后将恢复从用户设定的起始页开始抓取。")) return;
  await fetch("/api/scraper/checkpoint/clear", { method: "POST" });
  refreshCheckpointUI();
}

async function triggerPlaywright(mode) {
  const boardOrder = ["soaring", "hot", "new", "search"];
  const selectedBoards = boardOrder.filter((b) => {
    const el = document.querySelector(`.sync-board-chk[data-board="${b}"]`);
    return el && el.checked;
  });
  const boards = selectedBoards.length ? selectedBoards.join(",") : "soaring,hot,new";
  let categories = Array.from(document.querySelectorAll(".chk-scrape-cat:checked"))
    .map((el) => el.value)
    .join(",");
  if (!categories) {
    const topCat = document.getElementById("top-scrape-cat-select")?.value || "";
    if (topCat) categories = topCat;
  }
  const clampPg = (v, d) => Math.min(500, Math.max(1, parseInt(v, 10) || d));
  const pages = clampPg(
    document.getElementById("top-scrape-pages-select")?.value ||
      document.getElementById("scraper-pages-select")?.value ||
      "5",
    5
  );
  const startPage = clampPg(
    document.getElementById("top-scrape-start-page")?.value ||
      document.getElementById("scraper-start-page")?.value ||
      "1",
    1
  );

  const isSearchSelected = selectedBoards.includes("search");
  const isSearchOnly = isSearchSelected && selectedBoards.length === 1;
  const searchPagesVal = clampPg(document.getElementById("search-max-pages")?.value || pages, 500);
  const searchStartVal = clampPg(document.getElementById("search-start-page")?.value || startPage, 1);
  const effectiveStartPage = isSearchOnly ? searchStartVal : startPage;
  const effectivePages = isSearchOnly ? searchPagesVal : pages;

  try {
    const ck = await (await fetch("/api/scraper/checkpoint")).json();
    if (ck.has_checkpoint) {
      const ok = confirm(
        `发现上次未完成的进度（${ck.board_label} 第 ${ck.next_page} 页）。\n\n` +
        `点「确定」= 彻底清除该旧断点，严格从设定的第 ${effectiveStartPage} 页开始全新抓取；\n` +
        `点「取消」= 暂不开始（可改点「⏯ 恢复上次进度」从第 ${ck.next_page} 页续抓）。`
      );
      if (!ok) return;
      // 用户确认开始新抓取：必须立刻清除旧断点，刷新断点提示条
      await fetch("/api/scraper/checkpoint/clear", { method: "POST" });
      await refreshCheckpointUI();
    }
  } catch (e) {}

  renderLiveScrapeProgress({
    is_running: true,
    progress_pct: 6,
    message:
      mode === "cruise"
        ? `🛳️ 已启动【无人值守巡航】引擎，严格从第 ${effectiveStartPage} 页开始自动连续翻页（上限 ${effectivePages} 页）...`
        : `🚀 已发送一键快速采集指令，严格从第 ${effectiveStartPage} 页开始访问 FastMoss（上限 ${effectivePages} 页）...`,
  });

  if (
    await postTrigger({
      mode,
      boards,
      pages: effectivePages,
      start_page: effectiveStartPage,
      categories,
      search_pages: searchPagesVal,
      search_start: searchStartVal,
    })
  ) {
    startPollingLiveScrape();
  }
}

async function stopPlaywrightScrape() {
  await fetch("/api/scraper/stop", { method: "POST" });
  renderLiveScrapeProgress({
    is_running: false,
    progress_pct: 100,
    message: "⏹ 已发送安全停止信号，已抓到的商品数据与微缩图已全部保存入库（断点已记录，可随时恢复）！",
  });
  setTimeout(() => {
    loadDashboardData();
    refreshCheckpointUI();
  }, 1500);
}

async function triggerPlaywrightItem() {
  const target = document.getElementById("scraper-target-url").value.trim();
  if (!target) {
    alert("请先粘贴 FastMoss 商品详情链接或商品 ID");
    return;
  }
  renderLiveScrapeProgress({
    is_running: true,
    progress_pct: 20,
    message: `🎯 正在穿透抓取单品 (${target}) 全量详情...`,
  });
  await fetch("/api/scraper/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: "item", target }),
  });
  startPollingLiveScrape();
}

async function copyBridgeScript() {
  const scriptCode = `// FastMoss 墨西哥私有选品中枢 · 浏览器实时同步桥接器
(function(){
  const HUB = 'http://127.0.0.1:8688/api/ingest_raw';
  const origFetch = window.fetch;
  window.fetch = async function(...args){
    const resp = await origFetch.apply(this, args);
    try {
      resp.clone().json().then(data => {
        fetch(HUB, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({board:document.title, payload:data})}).catch(()=>{});
      }).catch(()=>{});
    } catch(e){}
    return resp;
  };
  console.log('✅ FastMoss 私有选品中枢桥接已激活 -> 127.0.0.1:8688');
})();`;
  await navigator.clipboard.writeText(scriptCode);
  alert("✅ 已复制 Chrome/油猴实时桥接脚本！");
}

async function copyReportMarkdown() {
  await navigator.clipboard.writeText(STATE.currentReportMarkdown || "");
  alert("✅ 已复制完整 Markdown 选品尽调报告！");
}

async function copyIdeCommand() {
  const cmd = STATE.currentIdeCommand || "请读取 exports/ 下的最新选品报告并帮我做深度策略研判";
  await navigator.clipboard.writeText(cmd);
  alert(`✅ 已复制联动指令：\n「${cmd}」\n\n现在直接粘贴到 Antigravity 聊天框发送给我，即可零 API 费用获得深度交互式选品诊断！`);
}

function openImportModal() {
  document.getElementById("modal-import").classList.add("open");
}

function openSettingsModal() {
  const pm = (STATE.config && STATE.config.profit_model) || {};
  const ai = (STATE.config && STATE.config.ai_engine) || {};
  document.getElementById("cfg-rate").value = pm.exchange_rate_mxn_per_rmb || 2.8;
  document.getElementById("cfg-fulfillment").value = pm.local_fulfillment_mxn || 30;
  document.getElementById("cfg-air-freight").value = pm.air_freight_rmb_per_kg || 75;
  document.getElementById("cfg-sea-freight").value = pm.sea_freight_rmb_per_kg || 20;
  document.getElementById("cfg-plat-fee").value = pm.platform_fee_rate || 0.09;
  document.getElementById("cfg-aff-fee").value = pm.affiliate_commission_rate || 0.12;
  document.getElementById("cfg-ai-url").value = ai.base_url || "https://api.deepseek.com/v1";
  document.getElementById("cfg-ai-model").value = ai.model || "deepseek-chat";
  document.getElementById("cfg-ai-key").value = ai.api_key || "";

  document.getElementById("modal-settings").classList.add("open");
}

function closeModals() {
  document.querySelectorAll(".modal-backdrop").forEach((el) => el.classList.remove("open"));
}

async function submitImportProduct() {
  const title_cn = document.getElementById("imp-title-cn").value.trim();
  const title_es = document.getElementById("imp-title-es").value.trim();
  const category = document.getElementById("imp-category").value.trim();
  const price_mxn = parseFloat(document.getElementById("imp-price").value) || 239;
  const sales_7d = parseInt(document.getElementById("imp-sales7d").value) || 200;
  const growth_rate_7d = parseFloat(document.getElementById("imp-growth").value) || 120;
  const creators_7d = parseInt(document.getElementById("imp-creators").value) || 10;
  const weight_g = parseFloat(document.getElementById("imp-weight").value) || 260;
  const cost_1688_rmb = parseFloat(document.getElementById("imp-cost").value) || 15;
  const csv_text = document.getElementById("imp-csv-text").value.trim();

  const items = [];
  if (title_cn || title_es) {
    items.push({
      title_cn: title_cn || title_es,
      title_es: title_es || title_cn,
      category,
      price_mxn,
      sales_7d,
      sales_28d: Math.round(sales_7d * 1.9),
      total_sales: Math.round(sales_7d * 2.4),
      growth_rate_7d,
      creators_7d,
      weight_g,
      cost_1688_rmb,
      daily_sales_series: [
        Math.round(sales_7d * 0.08),
        Math.round(sales_7d * 0.11),
        Math.round(sales_7d * 0.13),
        Math.round(sales_7d * 0.15),
        Math.round(sales_7d * 0.16),
        Math.round(sales_7d * 0.18),
        Math.round(sales_7d * 0.19),
      ],
      keywords_1688: [title_cn || title_es],
    });
  }

  const resp = await fetch("/api/product/add_or_import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items, csv_text }),
  });
  const data = await resp.json();
  closeModals();
  await loadDashboardData();
  alert(`✅ 成功导入并自动完成五维蓝海评分 (${data.imported || 0} 款商品)！`);
}

async function saveSettingsConfig() {
  const cfg = STATE.config || {};
  cfg.profit_model = cfg.profit_model || {};
  cfg.profit_model.exchange_rate_mxn_per_rmb = parseFloat(document.getElementById("cfg-rate").value) || 2.8;
  cfg.profit_model.local_fulfillment_mxn = parseFloat(document.getElementById("cfg-fulfillment").value) || 30;
  cfg.profit_model.air_freight_rmb_per_kg = parseFloat(document.getElementById("cfg-air-freight").value) || 75;
  cfg.profit_model.sea_freight_rmb_per_kg = parseFloat(document.getElementById("cfg-sea-freight").value) || 20;
  cfg.profit_model.platform_fee_rate = parseFloat(document.getElementById("cfg-plat-fee").value) || 0.09;
  cfg.profit_model.affiliate_commission_rate = parseFloat(document.getElementById("cfg-aff-fee").value) || 0.12;

  cfg.ai_engine = cfg.ai_engine || {};
  cfg.ai_engine.base_url = document.getElementById("cfg-ai-url").value.trim();
  cfg.ai_engine.model = document.getElementById("cfg-ai-model").value.trim();
  cfg.ai_engine.api_key = document.getElementById("cfg-ai-key").value.trim();

  await fetch("/api/config/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config: cfg }),
  });
  closeModals();
  await loadDashboardData();
  alert("✅ 墨西哥成本参数与 AI 引擎配置已保存，全库商品评分与毛利已自动重算！");
}

// ==================== FastMoss 四大 AI 工具箱 + 全能生图画板引擎 ====================
STATE.currentToolboxType = "voc_insight";
STATE.currentToolboxMarkdown = "";
STATE.studioLoadedImage = null;

function toggleToolboxSubmenu() {
  const sub = document.getElementById("toolbox-submenu");
  const arrow = document.getElementById("toolbox-submenu-arrow");
  if (!sub) return;
  if (sub.style.display === "none") {
    sub.style.display = "block";
    if (arrow) arrow.textContent = "▲";
  } else {
    sub.style.display = "none";
    if (arrow) arrow.textContent = "▼";
  }
}

function openToolbox(toolType, forcedProductId = "") {
  STATE.currentToolboxType = toolType || "voc_insight";

  // 切换主视图到 view-toolbox
  document.querySelectorAll(".view-panel").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-subitem").forEach((el) => el.classList.remove("active"));

  const targetView = document.getElementById("view-toolbox");
  if (targetView) targetView.classList.add("active");

  const navBox = document.getElementById("nav-toolbox");
  if (navBox) navBox.classList.add("active");

  const subNav = document.getElementById(`subnav-${STATE.currentToolboxType}`);
  if (subNav) subNav.classList.add("active");

  // 同步顶部胶囊按钮状态
  document.querySelectorAll("#toolbox-tabs-bar .cat-pill-btn").forEach((btn) => {
    if (btn.getAttribute("data-tbox") === STATE.currentToolboxType) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // 如果传了指定商品 ID，选中该商品
  const tboxSel = document.getElementById("toolbox-product-select");
  if (forcedProductId && tboxSel) {
    tboxSel.value = forcedProductId;
  }

  // 控制「全能生图画板」显示隐藏（在 image_studio 或 title_optimizer 下默认展开）
  const studioPanel = document.getElementById("toolbox-image-studio-panel");
  if (studioPanel) {
    if (STATE.currentToolboxType === "image_studio" || STATE.currentToolboxType === "title_optimizer") {
      studioPanel.style.display = "block";
      loadProductImageIntoStudio();
    } else {
      studioPanel.style.display = "none";
    }
  }

  runCurrentToolbox();
}

function onToolboxProductChange() {
  const studioPanel = document.getElementById("toolbox-image-studio-panel");
  if (studioPanel && studioPanel.style.display !== "none") {
    loadProductImageIntoStudio();
  }
  runCurrentToolbox();
}

async function runCurrentToolbox() {
  const tboxSel = document.getElementById("toolbox-product-select");
  const productId = tboxSel ? tboxSel.value : "";
  const customInput = document.getElementById("toolbox-custom-input")?.value || "";

  const titleEl = document.getElementById("toolbox-report-title");
  const bodyEl = document.getElementById("toolbox-markdown-content");
  if (titleEl) titleEl.textContent = "⏳ 正在运行 AI 工具箱专项引擎...";
  if (bodyEl) bodyEl.innerHTML = `<p style="color:var(--fm-pink);font-weight:600;">正在结合本地墨西哥商品库、拉美西语词库与 1688 供应链模型生成方案...</p>`;

  try {
    const resp = await fetch("/api/toolbox/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool_type: STATE.currentToolboxType,
        product_id: productId,
        custom_input: customInput,
      }),
    });
    const data = await resp.json();
    if (data.status === "ok") {
      if (titleEl) titleEl.textContent = data.title || "AI 工具箱分析结果";
      document.getElementById("toolbox-report-meta").textContent = `生成时间: ${data.created_at} | 绑定商品: ${data.product_title_cn} ($${data.price_mxn} MXN)`;
      STATE.currentToolboxMarkdown = data.report_markdown || "";
      if (bodyEl) bodyEl.innerHTML = renderMarkdown(STATE.currentToolboxMarkdown);

      // 更新生图画板上的默认价格标签
      const priceInput = document.getElementById("studio-price-badge");
      if (priceInput && data.price_mxn) {
        priceInput.value = `🔥 OFERTA $${Math.round(data.price_mxn)} MXN`;
      }
      if (STATE.currentToolboxType === "image_studio" || STATE.currentToolboxType === "title_optimizer") {
        renderMainImageCanvas();
      }
    }
  } catch (err) {
    console.error("Toolbox run error:", err);
  }
}

async function copyToolboxMarkdown() {
  await navigator.clipboard.writeText(STATE.currentToolboxMarkdown || "");
  alert("✅ 已复制当前 AI 工具箱方案全文！");
}

// ==================== 全能生图：HTML5 Canvas 墨西哥高点击西语首图合成器 ====================
function loadProductImageIntoStudio() {
  const pid = document.getElementById("toolbox-product-select")?.value;
  const prod = STATE.products.find((p) => p.product_id === pid) || STATE.products[0];
  if (!prod) {
    renderMainImageCanvas();
    return;
  }

  const priceInput = document.getElementById("studio-price-badge");
  if (priceInput && prod.price_mxn) {
    priceInput.value = `🔥 OFERTA $${Math.round(prod.price_mxn)} MXN`;
  }

  let imgUrl = prod.image_url || "";
  if (imgUrl && imgUrl.includes("/tt_shop/")) imgUrl = "";

  if (imgUrl) {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      STATE.studioLoadedImage = img;
      renderMainImageCanvas();
    };
    img.onerror = () => {
      STATE.studioLoadedImage = null;
      renderMainImageCanvas();
    };
    img.src = imgUrl;
  } else {
    STATE.studioLoadedImage = null;
    renderMainImageCanvas();
  }
}

function handleStudioImageUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      STATE.studioLoadedImage = img;
      renderMainImageCanvas();
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function applyStudioPreset(topTxt, bottomTxt, subTxt) {
  document.getElementById("studio-top-text").value = topTxt;
  document.getElementById("studio-bottom-text").value = bottomTxt;
  document.getElementById("studio-sub-badge").value = subTxt;
  renderMainImageCanvas();
}

function renderMainImageCanvas() {
  const canvas = document.getElementById("main-image-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;

  const theme = document.getElementById("studio-theme")?.value || "tiktok_pink";
  const topText = document.getElementById("studio-top-text")?.value || "🇲🇽 ENVÍO RÁPIDO DESDE MÉXICO";
  const priceText = document.getElementById("studio-price-badge")?.value || "🔥 OFERTA $299 MXN";
  const subBadge = document.getElementById("studio-sub-badge")?.value || "100% CALIDAD PREMIUM";
  const bottomText = document.getElementById("studio-bottom-text")?.value || "FÁCIL DE USAR · AHORRA ESPACIO";

  const pid = document.getElementById("toolbox-product-select")?.value;
  const prod = STATE.products.find((p) => p.product_id === pid) || STATE.products[0] || {};

  // 主题色配置
  const palettes = {
    tiktok_pink: {
      bgGrad: ["#fff5f7", "#ffffff"],
      topBg: "#009c3b", // 墨西哥国旗绿信任标
      topFg: "#ffffff",
      bottomBg: "#fe2c55", // TikTok 爆款玫红
      bottomFg: "#ffffff",
      priceBg: "#ff3141",
      borderCol: "#fe2c55",
    },
    mexico_green: {
      bgGrad: ["#f0fdf4", "#ffffff"],
      topBg: "#047857",
      topFg: "#ffffff",
      bottomBg: "#065f46",
      bottomFg: "#fef08a",
      priceBg: "#ea580c",
      borderCol: "#059669",
    },
    promo_gold: {
      bgGrad: ["#18181b", "#27272a"],
      topBg: "#f59e0b",
      topFg: "#111827",
      bottomBg: "#111827",
      bottomFg: "#fde047",
      priceBg: "#e11d48",
      borderCol: "#f59e0b",
    },
    clean_blue: {
      bgGrad: ["#eff6ff", "#ffffff"],
      topBg: "#1d4ed8",
      topFg: "#ffffff",
      bottomBg: "#1e3a8a",
      bottomFg: "#ffffff",
      priceBg: "#fe2c55",
      borderCol: "#2563eb",
    },
  };
  const pal = palettes[theme] || palettes.tiktok_pink;

  // 1. 背景绘制
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, pal.bgGrad[0]);
  grad.addColorStop(1, pal.bgGrad[1]);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // 2. 绘制中间商品主图（或高质感占位卡片）
  const imgBoxY = 92;
  const imgBoxH = H - 200;
  if (STATE.studioLoadedImage) {
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(60, imgBoxY, W - 120, imgBoxH, 24);
    ctx.clip();
    ctx.drawImage(STATE.studioLoadedImage, 60, imgBoxY, W - 120, imgBoxH);
    ctx.restore();
  } else {
    ctx.fillStyle = theme === "promo_gold" ? "#3f3f46" : "#ffffff";
    ctx.beginPath();
    ctx.roundRect(70, imgBoxY + 10, W - 140, imgBoxH - 20, 28);
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#e2e8f0";
    ctx.stroke();

    ctx.fillStyle = theme === "promo_gold" ? "#fde047" : "#1e293b";
    ctx.font = "bold 34px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "center";
    const esTitle = (prod.title_es || prod.title_cn || "PRODUCTO ESTRELLA MÉXICO").slice(0, 28);
    ctx.fillText(esTitle, W / 2, H / 2 - 15);

    ctx.fillStyle = "#64748b";
    ctx.font = "600 22px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.fillText("📂 点击下方「上传本地/1688商品图」替换实拍主图", W / 2, H / 2 + 35);
  }

  // 3. 顶部墨西哥本土仓信任横幅
  ctx.fillStyle = pal.topBg;
  ctx.fillRect(0, 0, W, 76);
  ctx.fillStyle = pal.topFg;
  ctx.font = "900 31px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(topText, W / 2, 39);

  // 4. 左上角价格爆炸贴 (圆角胶囊)
  ctx.save();
  ctx.fillStyle = pal.priceBg;
  ctx.shadowColor = "rgba(0,0,0,0.22)";
  ctx.shadowBlur = 14;
  ctx.beginPath();
  ctx.roundRect(24, 96, 330, 68, 34);
  ctx.fill();
  ctx.restore();

  ctx.fillStyle = "#ffffff";
  ctx.font = "900 27px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(priceText, 24 + 165, 96 + 35);

  // 5. 右下角品质保证角标
  ctx.save();
  ctx.fillStyle = "#111827";
  ctx.beginPath();
  ctx.roundRect(W - 310, H - 182, 286, 54, 14);
  ctx.fill();
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "#fde047";
  ctx.stroke();
  ctx.restore();

  ctx.fillStyle = "#fde047";
  ctx.font = "800 21px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(`⭐ ${subBadge}`, W - 310 + 143, H - 182 + 28);

  // 6. 底部大字核心西语痛点卖点横幅
  ctx.fillStyle = pal.bottomBg;
  ctx.fillRect(0, H - 104, W, 104);
  ctx.fillStyle = pal.bottomFg;
  ctx.font = "900 29px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(bottomText, W / 2, H - 52);

  // 7. 整体外边框高亮勾勒（提升移动端信息流注意力）
  ctx.lineWidth = 12;
  ctx.strokeStyle = pal.borderCol;
  ctx.strokeRect(6, 6, W - 12, H - 12);
}

function downloadCanvasMainImage() {
  const canvas = document.getElementById("main-image-canvas");
  if (!canvas) return;
  const pid = document.getElementById("toolbox-product-select")?.value || "MX";
  const link = document.createElement("a");
  link.download = `tiktok_mx_main_${pid}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
}

// ==================== 首页四大胶囊切换 & 🎬 带货视频 (Seedance 2.0 + 9:16 竖屏合成引擎) ====================
STATE.homeTopMode = "insight";
STATE.videoRefImage = null;
STATE.videoAnimFrame = null;

function switchHomeTopMode(mode, btnEl) {
  STATE.homeTopMode = mode || "insight";
  document.querySelectorAll("#home-top-mode-pills .mode-pill").forEach((b) => b.classList.remove("active"));
  if (btnEl) {
    btnEl.classList.add("active");
  } else {
    const targetBtn = document.querySelector(`#home-top-mode-pills .mode-pill[data-hmode="${mode}"]`);
    if (targetBtn) targetBtn.classList.add("active");
  }

  const inputEl = document.getElementById("agent-custom-input");
  const defaultToolbar = document.getElementById("toolbar-mode-default");
  const videoToolbar = document.getElementById("toolbar-mode-video");
  const fbeanBadge = document.getElementById("video-fbean-badge");
  const videoStudioCard = document.getElementById("agent-video-studio-card");
  const expertBadge = document.getElementById("home-expert-badge");

  if (mode === "video") {
    // 1:1 复刻截图「🎬 带货视频」控制台
    if (inputEl) {
      inputEl.placeholder = "输入商品卖点、人群特征和参考内容，生成适合投放的带货视频方案。";
    }
    if (defaultToolbar) defaultToolbar.style.display = "none";
    if (videoToolbar) videoToolbar.style.display = "flex";
    if (fbeanBadge) fbeanBadge.style.display = "inline-block";
    if (videoStudioCard) {
      videoStudioCard.style.display = "block";
      syncVideoStudioWithProduct();
    }
    filterPromptLibrary("CONTENT", null);
  } else if (mode === "creator") {
    if (inputEl) {
      inputEl.placeholder = "输入目标商品与佣金预算，为您匹配高出单率的墨西哥本土带货达人画像并生成拉美西语建联寄样话术...";
    }
    if (defaultToolbar) defaultToolbar.style.display = "flex";
    if (videoToolbar) videoToolbar.style.display = "none";
    if (fbeanBadge) fbeanBadge.style.display = "none";
    if (videoStudioCard) videoStudioCard.style.display = "none";
    if (expertBadge) expertBadge.textContent = "🤝 达人建联模式 · 墨西哥 5K~100K 腰尾部寄样策略";
    filterPromptLibrary("CREATOR", null);
  } else if (mode === "image") {
    // 直接打开全能生图画板
    openToolbox("image_studio", document.getElementById("agent-product-selector")?.value || "");
    return;
  } else {
    // 默认数据洞察
    if (inputEl) {
      inputEl.placeholder = "对 @商品 做一份 TikTok Shop 墨西哥选品尽调：目标人群、西语卖点、竞品价格带、短视频前3秒脚本、NOM合规风险点与 1688 空运/海运测款账本...";
    }
    if (defaultToolbar) defaultToolbar.style.display = "flex";
    if (videoToolbar) videoToolbar.style.display = "none";
    if (fbeanBadge) fbeanBadge.style.display = "none";
    if (videoStudioCard) videoStudioCard.style.display = "none";
    if (expertBadge) expertBadge.textContent = "🎯 专家模式 · 墨西哥本地囤货策略";
    filterPromptLibrary("ALL", null);
  }
}

function onAgentProductSelectChange() {
  if (STATE.homeTopMode === "video") {
    syncVideoStudioWithProduct();
  }
}

async function submitHomeAgentAction() {
  const pid = document.getElementById("agent-product-selector")?.value || "";
  const customInput = document.getElementById("agent-custom-input")?.value || "";

  if (STATE.homeTopMode === "video") {
    const modelName = document.getElementById("video-gen-model")?.value || "Seedance 2.0 Fast";
    const specStr = document.getElementById("video-gen-spec")?.value || "720p|9:16|5";
    const langStr = document.getElementById("video-gen-lang")?.value || "es-MX";

    document.getElementById("report-title").textContent = `⏳ 正在通过 [${modelName}] 引擎生成 9:16 带货视频与投放方案...`;
    document.getElementById("report-markdown-content").innerHTML = `<p style="color:var(--fm-pink);font-weight:600;">正在合成 9:16 竖屏关键帧、拉美西语动态花字与 Seedance 2.0 运镜指令...</p>`;

    try {
      const resp = await fetch("/api/toolbox/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool_type: "seedance_video_gen",
          product_id: pid,
          custom_input: `[模型:${modelName} | 规格:${specStr} | 语言:${langStr}] ${customInput}`,
        }),
      });
      const data = await resp.json();
      if (data.status === "ok") {
        displayReport({
          title: data.title,
          created_at: data.created_at,
          report_markdown: data.report_markdown,
        });
        const sd = data.structured_data || {};
        if (sd.keyframes && sd.keyframes.length >= 3) {
          document.getElementById("vid-cap-1").value = sd.keyframes[0].caption_es;
          document.getElementById("vid-cap-2").value = sd.keyframes[1].caption_es;
          document.getElementById("vid-cap-3").value = sd.keyframes[2].caption_es;
        }
        if (sd.tts_full_es) {
          document.getElementById("vid-tts-script").value = sd.tts_full_es;
        }
        if (sd.seedance_prompt_en) {
          document.getElementById("vid-seedance-prompt").value = sd.seedance_prompt_en;
        }
        playTikTokVerticalVideo(true);
      }
    } catch (e) {
      console.error("Video gen error:", e);
    }
    return;
  }

  if (STATE.homeTopMode === "creator") {
    runAgentWorkflow("creator_outreach_es", pid);
    return;
  }

  runAgentWorkflow("product_due_diligence", pid);
}

function handleVideoRefImageUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      STATE.videoRefImage = img;
      drawTikTokVideoFrame(0.8);
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function updateVideoPreviewSettings() {
  syncVideoStudioWithProduct();
}

function syncVideoStudioWithProduct() {
  const pid = document.getElementById("agent-product-selector")?.value;
  const prod = STATE.products.find((p) => p.product_id === pid) || STATE.products[0];
  if (!prod) return;

  const pEs = prod.title_es || prod.title_cn || "Producto Estrella";
  const priceMxn = Math.round(prod.price_mxn || 299);
  const subCat = getSubCategory(prod);

  document.getElementById("vid-cap-1").value = `¡NO COMPRES OTRO SIN VER ESTO! 😱`;
  document.getElementById("vid-cap-2").value = `✨ ${pEs.slice(0, 22).toUpperCase()}`;
  document.getElementById("vid-cap-3").value = `🇲🇽 ENVÍO DESDE MÉXICO · $${priceMxn} MXN`;
  document.getElementById("vid-tts-script").value = `¡No compres otro más sin ver esto! Mira este ${pEs}, súper práctico, resistente y con envío rápido desde México por solo ${priceMxn} pesos. ¡Haz clic en el carrito naranja abajo!`;
  document.getElementById("vid-seedance-prompt").value = `Vertical 9:16 TikTok commercial video of ${pEs} (${subCat}). 0-2s: Fast dynamic zoom-in on the product held by a young Mexican creator in a bright warm home, surprised expression. 2-4s: Smooth macro orbital camera movement showcasing ${pEs} solving daily problems in 3 seconds, crisp 60fps lighting. 4-5s: Hero product shot with Mexico local fast shipping package badge.`;

  let imgUrl = prod.image_url || "";
  if (imgUrl && imgUrl.includes("/tt_shop/")) imgUrl = "";

  if (imgUrl) {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      STATE.videoRefImage = img;
      drawTikTokVideoFrame(0.6);
    };
    img.onerror = () => {
      STATE.videoRefImage = null;
      drawTikTokVideoFrame(0.6);
    };
    img.src = imgUrl;
  } else {
    STATE.videoRefImage = null;
    drawTikTokVideoFrame(0.6);
  }
}

function drawTikTokVideoFrame(elapsedSec = 0) {
  const canvas = document.getElementById("tiktok-video-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width; // 720
  const H = canvas.height; // 1280

  const specStr = document.getElementById("video-gen-spec")?.value || "720p|9:16|5";
  const totalSec = parseFloat(specStr.split("|")[2] || "5");
  const progress = Math.min(1, Math.max(0, elapsedSec / totalSec));

  const pid = document.getElementById("agent-product-selector")?.value;
  const prod = STATE.products.find((p) => p.product_id === pid) || STATE.products[0] || {};
  const pEs = prod.title_es || prod.title_cn || "Producto TikTok Shop México";
  const priceMxn = Math.round(prod.price_mxn || 299);
  const subCat = getSubCategory(prod);

  // 1. 深色电影感渐变背景
  const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  bgGrad.addColorStop(0, "#1e1b4b");
  bgGrad.addColorStop(0.5, "#0f172a");
  bgGrad.addColorStop(1, "#090d16");
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  // 2. 动态 Ken Burns 推镜与摇镜计算 (模拟 Seedance 2.0 镜头运动)
  const zoom = 1.0 + 0.16 * Math.sin(progress * Math.PI);
  const panX = Math.sin(progress * Math.PI * 2) * 18;
  const panY = Math.cos(progress * Math.PI) * 14;

  ctx.save();
  ctx.beginPath();
  ctx.roundRect(44, 190, W - 88, 680, 32);
  ctx.clip();

  if (STATE.videoRefImage) {
    const iw = (W - 88) * zoom;
    const ih = 680 * zoom;
    const ix = 44 - (iw - (W - 88)) / 2 + panX;
    const iy = 190 - (ih - 680) / 2 + panY;
    ctx.drawImage(STATE.videoRefImage, ix, iy, iw, ih);
  } else {
    // 科技感动态商品展示卡片
    const cardGrad = ctx.createLinearGradient(44, 190, W - 44, 870);
    cardGrad.addColorStop(0, "#fff1f2");
    cardGrad.addColorStop(1, "#ffe4e6");
    ctx.fillStyle = cardGrad;
    ctx.fillRect(44, 190, W - 88, 680);

    ctx.fillStyle = "#e11d48";
    ctx.font = "900 44px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`🇲🇽 ${subCat}`, W / 2 + panX * 0.4, 460 + panY * 0.4);

    ctx.fillStyle = "#1e293b";
    ctx.font = "bold 32px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.fillText(pEs.slice(0, 26), W / 2, 535);

    ctx.fillStyle = "#64748b";
    ctx.font = "600 24px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.fillText("📎 可点击上方「参考图」上传 1688 实拍图", W / 2, 600);
  }
  ctx.restore();

  // 3. 顶部 TikTok Shop 墨西哥本土发货绿标
  ctx.save();
  ctx.fillStyle = "#009c3b";
  ctx.beginPath();
  ctx.roundRect(44, 68, W - 88, 72, 36);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "900 29px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("🇲🇽 ENVÍO RÁPIDO DESDE MÉXICO · 2-3 DÍAS", W / 2, 104);
  ctx.restore();

  // 4. 根据当前秒数切换 3 段式爆款动态花字 (0-36% / 36-72% / 72-100%)
  let activeCaption = document.getElementById("vid-cap-1")?.value || "¡NO COMPRES OTRO SIN VER ESTO!";
  let stageBadge = "🔥 HOOK · 黄金前3秒痛点钩子";
  let bannerBg = "#fe2c55";

  if (progress >= 0.36 && progress < 0.72) {
    activeCaption = document.getElementById("vid-cap-2")?.value || "✨ RESULTADO EN 3 SEGUNDOS";
    stageBadge = "⚡ DEMO · 核心功能微距实测";
    bannerBg = "#059669";
  } else if (progress >= 0.72) {
    activeCaption = document.getElementById("vid-cap-3")?.value || `🇲🇽 OFERTA HOY: $${priceMxn} MXN`;
    stageBadge = "🛒 CTA · 左下角小黄车限时促单";
    bannerBg = "#ea580c";
  }

  // 弹跳花字条
  const pulse = 1 + 0.03 * Math.sin(elapsedSec * 12);
  ctx.save();
  ctx.translate(W / 2, 935);
  ctx.scale(pulse, pulse);
  ctx.fillStyle = bannerBg;
  ctx.shadowColor = "rgba(0,0,0,0.45)";
  ctx.shadowBlur = 18;
  ctx.beginPath();
  ctx.roundRect(-320, -48, 640, 96, 22);
  ctx.fill();

  ctx.fillStyle = "#ffffff";
  ctx.font = "900 30px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(activeCaption.slice(0, 32), 0, -6);

  ctx.fillStyle = "#fef08a";
  ctx.font = "700 20px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText(stageBadge, 0, 26);
  ctx.restore();

  // 5. 仿 TikTok 左下角小黄车商品挂载卡片 (TikTok Shop Anchor Card)
  ctx.save();
  ctx.fillStyle = "rgba(255, 255, 255, 0.96)";
  ctx.beginPath();
  ctx.roundRect(40, 1025, 490, 140, 20);
  ctx.fill();

  // 橙色小黄车图标框
  ctx.fillStyle = "#ff5500";
  ctx.beginPath();
  ctx.roundRect(58, 1045, 96, 100, 16);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "900 42px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("🛒", 106, 1102);

  // 商品标题与墨西哥比索价格
  ctx.textAlign = "left";
  ctx.fillStyle = "#0f172a";
  ctx.font = "800 24px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText(pEs.slice(0, 20), 172, 1072);

  ctx.fillStyle = "#fe2c55";
  ctx.font = "900 32px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText(`$${priceMxn} MXN`, 172, 1114);

  ctx.fillStyle = "#059669";
  ctx.font = "700 19px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillText("⚡ Comprar ahora · Envío Gratis", 172, 1146);
  ctx.restore();

  // 6. 右侧 TikTok 点赞/评论/分享悬浮栏仿真
  ctx.save();
  ctx.fillStyle = "#ffffff";
  ctx.font = "700 26px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("❤️", W - 68, 990);
  ctx.font = "600 18px sans-serif";
  ctx.fillText("12.8K", W - 68, 1020);
  ctx.font = "700 26px sans-serif";
  ctx.fillText("💬", W - 68, 1070);
  ctx.font = "600 18px sans-serif";
  ctx.fillText("486", W - 68, 1100);
  ctx.restore();

  // 7. 底部播放进度条
  ctx.fillStyle = "rgba(255,255,255,0.22)";
  ctx.fillRect(0, H - 14, W, 14);
  ctx.fillStyle = "#fe2c55";
  ctx.fillRect(0, H - 14, W * progress, 14);
}

function playTikTokVerticalVideo(withVoice = true) {
  if (STATE.videoAnimFrame) {
    cancelAnimationFrame(STATE.videoAnimFrame);
  }
  const specStr = document.getElementById("video-gen-spec")?.value || "720p|9:16|5";
  const totalSec = parseFloat(specStr.split("|")[2] || "5");
  const langCode = document.getElementById("video-gen-lang")?.value || "es-MX";
  const ttsText = document.getElementById("vid-tts-script")?.value || "";

  // 启动浏览器原生拉美西语 TTS 语音播报
  if (withVoice && "speechSynthesis" in window && ttsText) {
    try {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(ttsText);
      utter.lang = langCode;
      utter.rate = 1.08;
      window.speechSynthesis.speak(utter);
    } catch (e) {}
  }

  const startTs = performance.now();
  const statusEl = document.getElementById("video-player-status");

  function step(now) {
    const elapsed = (now - startTs) / 1000.0;
    if (elapsed <= totalSec) {
      drawTikTokVideoFrame(elapsed);
      if (statusEl) {
        statusEl.textContent = `▶️ 正在播放 9:16 竖屏 (${elapsed.toFixed(1)}s / ${totalSec.toFixed(1)}s)`;
      }
      STATE.videoAnimFrame = requestAnimationFrame(step);
    } else {
      drawTikTokVideoFrame(totalSec);
      if (statusEl) {
        statusEl.textContent = `✅ 播放完成 (${totalSec.toFixed(1)}s · 9:16 竖屏)`;
      }
    }
  }
  STATE.videoAnimFrame = requestAnimationFrame(step);
}

function exportTikTokVerticalVideo() {
  const canvas = document.getElementById("tiktok-video-canvas");
  if (!canvas || typeof canvas.captureStream !== "function") {
    alert("当前浏览器环境不支持 Canvas 视频流录制，请使用 Chrome 浏览器。");
    return;
  }

  const specStr = document.getElementById("video-gen-spec")?.value || "720p|9:16|5";
  const totalSec = parseFloat(specStr.split("|")[2] || "5");
  const pid = document.getElementById("agent-product-selector")?.value || "MX";
  const btn = document.getElementById("btn-record-video");
  if (btn) btn.textContent = "🔴 正在录制 9:16 视频成片...";

  const stream = canvas.captureStream(30);
  const chunks = [];
  let recorder;
  try {
    recorder = new MediaRecorder(stream, { mimeType: "video/webm;codecs=vp9" });
  } catch (e) {
    recorder = new MediaRecorder(stream);
  }

  recorder.ondataavailable = (ev) => {
    if (ev.data && ev.data.size > 0) chunks.push(ev.data);
  };

  recorder.onstop = () => {
    const blob = new Blob(chunks, { type: "video/webm" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tiktok_mx_9x16_${pid}.webm`;
    a.click();
    if (btn) btn.textContent = "💾 录制并导出 9:16 视频成片 (.webm)";
  };

  recorder.start();
  playTikTokVerticalVideo(false);
  setTimeout(() => {
    if (recorder.state === "recording") {
      recorder.stop();
    }
  }, totalSec * 1000 + 250);
}

async function copySeedancePrompt() {
  const txt = document.getElementById("vid-seedance-prompt")?.value || "";
  await navigator.clipboard.writeText(txt);
  alert("✅ 已复制 Seedance 2.0 / Kling / Veo 图生视频导演级运镜指令！");
}

window.addEventListener("DOMContentLoaded", () => {
  renderScrapeCategoryChips();
  updateSearchRangeBox();
  refreshCheckpointUI();
  const sortEl = document.getElementById("filter-sort");
  if (sortEl) {
    sortEl.addEventListener("change", onSortChange);
  }
  loadDashboardData();
});
