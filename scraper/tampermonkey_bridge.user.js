// ==UserScript==
// @name         FastMoss 墨西哥私有选品中枢 · 实时数据桥接器 (标准版/旗舰版通用)
// @namespace    http://127.0.0.1:8688/
// @version      1.0.0
// @description  在正常浏览 FastMoss 网页版时，自动拦截商品列表与单品详情底层 JSON 数据并实时同步到本地私有化选品中枢 (127.0.0.1:8688)
// @author       Antigravity Private Hub
// @match        *://*.fastmoss.com/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';
    const HUB_ENDPOINT = 'http://127.0.0.1:8688/api/ingest_raw';

    function pushToLocalHub(payload, sourceUrl) {
        fetch(HUB_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_url: sourceUrl,
                board: document.title || 'FastMoss网页端实时伴随',
                payload: payload
            })
        }).catch(() => {});
    }

    // 拦截 fetch
    const origFetch = window.fetch;
    window.fetch = async function (...args) {
        const response = await origFetch.apply(this, args);
        try {
            const clone = response.clone();
            const ctype = clone.headers.get('content-type') || '';
            if (ctype.includes('application/json')) {
                clone.json().then(data => pushToLocalHub(data, response.url)).catch(() => {});
            }
        } catch (e) {}
        return response;
    };

    // 拦截 XMLHttpRequest
    const origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
        this._fm_url = url;
        return origOpen.apply(this, arguments);
    };
    const origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
        this.addEventListener('load', function () {
            try {
                if (this.responseText && this.responseText.trim().startsWith('{')) {
                    const data = JSON.parse(this.responseText);
                    pushToLocalHub(data, this._fm_url || location.href);
                }
            } catch (e) {}
        });
        return origSend.apply(this, arguments);
    };

    console.log('✅ [FastMoss 私有选品中枢桥接器] 已激活 -> 数据将自动同步至 http://127.0.0.1:8688');
})();
