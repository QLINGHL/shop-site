/* 前端保护：域名锁定 + 防右键/快捷键 + 反调试 + 防嵌套 */
(function () {
  // ---- 1. 域名锁定：非授权域名直接清空 ----
  var ALLOW = ['qlinghl.alwaysdata.net', 'qlinghl.com', 'www.qlinghl.com',
               'shop.qlinghl.workers.dev',
               'localhost', '127.0.0.1', ''];
  var host = '';
  try { host = window.location.hostname || ''; } catch (e) {}
  if (ALLOW.indexOf(host) < 0) {
    try { document.documentElement.innerHTML = ''; } catch (e2) {}
    try { window.location.href = 'about:blank'; } catch (e3) {}
    throw new Error('denied');
  }

  // ---- 2. 防 iframe 嵌套盗用 ----
  try {
    if (window.top !== window.self) { window.top.location = window.self.location; }
  } catch (e) {}

  // ---- 3. 禁右键 / 禁拖拽（保留文字选择与复制，方便客户复制卡密/账号） ----
  document.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  document.addEventListener('dragstart', function (e) { e.preventDefault(); });

  // ---- 4. 禁 F12 / Ctrl+U / Ctrl+S / Ctrl+Shift+I/J/C ----
  document.addEventListener('keydown', function (e) {
    var k = e.keyCode || e.which;
    if (k === 123) { e.preventDefault(); return; }                       // F12
    if ((e.ctrlKey || e.metaKey) && (k === 85 || k === 83)) { e.preventDefault(); return; } // U/S
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (k === 73 || k === 74 || k === 67)) { e.preventDefault(); return; } // Shift+I/J/C
    if ((e.ctrlKey || e.metaKey) && e.altKey && (k === 73 || k === 74)) { e.preventDefault(); } // Alt+I/J
  });

  // ---- 5. 反调试：dock 式 devtools 检测（移动端跳过：手机 Safari 地址栏显隐会导致内外高度差误杀） ----
  (function () {
    var isMobile5 = false;
    try { isMobile5 = /Mobile|Android|iPhone|iPad|iPod/i.test(navigator.userAgent || ''); } catch (e) {}
    if (isMobile5) return;
    setInterval(function () {
      try {
        var dw = Math.abs(window.outerWidth - window.innerWidth);
        var dh = Math.abs(window.outerHeight - window.innerHeight);
        if (dw > 200 || dh > 200) {
          document.documentElement.innerHTML = '';
          throw new Error('denied');
        }
      } catch (e) {}
    }, 1200);
  })();

  // ---- 6. 反自动化抓取：自动化浏览器直接不渲染 ----
  (function () {
    var bot = false;
    try {
      var ua = navigator.userAgent || '';
      // 6a. 标准自动化标记（Selenium / Playwright / browser-use 默认都会带）
      if (navigator.webdriver === true) bot = true;
      // 6b. UA 特征（含 browser-use 等 AI 浏览器框架）
      if (/HeadlessChrome|Headless|PhantomJS|Playwright|Puppeteer|Selenium|browser-use/i.test(ua)) bot = true;
      // 6c. 自动化框架注入的全局对象
      if (window.__playwright || window.__pwInitScripts || window._selenium || window.callSelenium) bot = true;
      try { if (document.__selenium_evaluate || document.__webdriver_evaluate) bot = true; } catch (e0) {}
      // 6d. 已删除：navigator.plugins 检测（误杀太多——平板桌面模式、WebView、隐私浏览器都可能为 0）
      // 可靠检测只保留 webdriver / UA 关键词 / 自动化全局对象
    } catch (e) {}
    if (bot) {
      try { document.documentElement.innerHTML = ''; } catch (e2) {}
      try { window.location.href = 'about:blank'; } catch (e3) {}
      throw new Error('denied');
    }
  })();
})();
