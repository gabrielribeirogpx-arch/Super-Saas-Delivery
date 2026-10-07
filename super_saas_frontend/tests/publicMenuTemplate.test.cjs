const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const puppeteer = require('puppeteer-core');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
const originalLoad = Module._load;
const stub = () => null;
// Isolate the renderer from checkout/PWA integrations; use its real markup and CSS.
Module._load = function(request, parent, isMain) {
  if (request.endsWith('.module.css')) return { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) };
  if (request === 'next/image') return { __esModule: true, default: ({ fill, ...props }) => React.createElement('img', props) };
  if (request.startsWith('@/components/') && !request.includes('PublicMenuPage')) {
    return new Proxy({ default: stub }, { get: (obj, key) => obj[key] || stub });
  }
  if (request.startsWith('@/lib/')) request = path.join(root, request.slice(2)) + '.ts';
  return originalLoad.call(this, request, parent, isMain);
};
for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
}
const { PublicMenuPage } = require('../components/PublicMenu/PublicMenuPage.tsx');
Module._load = originalLoad;
const menu = {
  slug: 'loja', tenant_id: 1, tenant: { name: 'Sabores da Casa com um nome bem longo', estimated_prep_time: '25-40 min' },
  public_settings: { theme: 'white', primary_color: '#dc2626' },
  categories: [{ id: 1, name: 'Categoria com nome longo', items: [{ id: 1, name: 'Hambúrguer da Casa', description: 'Uma descrição longa '.repeat(15), price_cents: 2990, featured: true }] }],
  items_without_category: [],
};
const render = (value = menu, props = {}) => renderToStaticMarkup(React.createElement(PublicMenuPage, { menu: value, ...props }));
test('public and administrative preview share PublicMenuPage', () => {
  const publicSource = fs.readFileSync(path.join(root, 'components/storefront/StorefrontMenuContent.tsx'), 'utf8');
  const previewSource = fs.readFileSync(path.join(root, 'app/(admin)/storefront-preview/page.tsx'), 'utf8');
  for (const source of [publicSource, previewSource]) {
    assert.match(source, /import \{ PublicMenuPage \} from "@\/components\/PublicMenu\/PublicMenuPage"/);
    assert.match(source, /<PublicMenuPage menu=/);
  }
  for (const html of [render(), render(menu, { enableCart: false, forcedTheme: 'white', hideThemeToggle: true })]) {
    assert.match(html, /defaultTemplate/);
    assert.match(html, /data-has-cover="false"/);
    assert.match(html, /logoFallback/);
    assert.match(html, /Hambúrguer da Casa/);
  }
});
test('legacy/custom menus keep legacy styles and uploaded assets take priority', () => {
  for (const settings of [{ theme: 'dark', primary_color: '#2563eb' }, { theme: 'white', primary_color: '#123456' }]) {
    assert.doesNotMatch(render({ ...menu, public_settings: settings }), /defaultTemplate|logoFallback/);
  }
  const html = render({ ...menu, public_settings: { ...menu.public_settings, logo_url: '/logo.png', cover_image_url: '/cover.png' } });
  assert.match(html, /data-has-cover="true"/);
  assert.match(html, /src="\/cover.png"/);
  assert.match(html, /src="\/logo.png"/);
  assert.doesNotMatch(html, /logoFallback/);
});
test('fallback layout fits 320, 360, 390 and 430px in Chromium', { skip: !fs.existsSync('/usr/bin/chromium') }, async () => {
  const css = fs.readFileSync(path.join(root, 'styles/menu-tokens.css'), 'utf8') + fs.readFileSync(path.join(root, 'components/PublicMenu/PublicMenu.module.css'), 'utf8');
  const variants = [render(), render({ ...menu, categories: [] }), render(menu, { enableCart: false, forcedTheme: 'white', hideThemeToggle: true })];
  const frames = [320, 360, 390, 430].flatMap(width => variants.map(markup => {
    const content = `<style>*{box-sizing:border-box}body{margin:0}${css}</style>${markup}`;
    return `<iframe width="${width}" height="1200" srcdoc="${content.replaceAll('&', '&amp;').replaceAll('"', '&quot;')}"></iframe>`;
  })).join('');
  const dir = fs.mkdtempSync('/tmp/public-menu-layout-');
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
      headless: true, userDataDir: `${dir}/browser`,
      args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking'],
      env: { ...process.env, XDG_CACHE_HOME: dir, XDG_CONFIG_HOME: dir },
    });
    const page = await browser.newPage();
    await page.setContent(frames);
    const results = await page.evaluate(() => [...document.querySelectorAll('iframe')].map(f => {
      const d = f.contentDocument;
      const image = d.querySelector('.highlightMedia');
      return {
        width: Number(f.width), scroll: d.documentElement.scrollWidth,
        height: d.querySelector('.hero').getBoundingClientRect().height,
        overlay: getComputedStyle(d.querySelector('.heroOverlay')).display,
        ratio: image ? image.clientWidth / image.clientHeight : null,
      };
    }));
    assert.equal(results.length, 12);
    for (const result of results) {
      assert.ok(result.scroll <= result.width, JSON.stringify(result));
      assert.equal(result.height, 232);
      assert.equal(result.overlay, 'none');
      if (result.ratio) assert.ok(Math.abs(result.ratio - 4 / 3) < .03);
    }
  } finally {
    if (browser) await browser.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
