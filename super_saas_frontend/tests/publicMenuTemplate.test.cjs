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
  const previewSource = fs.readFileSync(path.join(root, 'app/storefront-preview-frame/page.tsx'), 'utf8');
  for (const source of [publicSource, previewSource]) {
    assert.match(source, /import \{ PublicMenuPage \} from "@\/components\/PublicMenu\/PublicMenuPage"/);
    assert.match(source, /<PublicMenuPage\s+menu=/);
  }
  const editorSource = fs.readFileSync(path.join(root, 'app/(admin)/storefront-preview/page.tsx'), 'utf8');
  assert.match(editorSource, /<iframe[^>]+src="\/storefront-preview-frame"/);
  for (const html of [render(), render(menu, { enableCart: false, forcedTheme: 'white' })]) {
    assert.match(html, /defaultTemplate/);
    assert.match(html, /--premium-accent:#dc2626/);
    assert.match(html, /data-has-cover="false"/);
    assert.match(html, /logoFallback/);
    assert.match(html, /Hambúrguer da Casa/);
    assert.match(html, /Tenha a Sabores da Casa com um nome bem longo no seu celular/);
  }
});
test('public menu and preview use the same saved colors, typography and layout in both themes', () => {
  const settings = { ...menu.public_settings, secondary_color: '#abcdef', button_radius: 18, font_family: 'Roboto' };
  for (const theme of ['white', 'dark']) {
    const withTheme = { ...menu, public_settings: { ...settings, theme } };
    const publicHtml = render(withTheme);
    const previewHtml = render(withTheme, { enableCart: false, forcedTheme: theme });
    for (const html of [publicHtml, previewHtml]) {
      assert.match(html, /defaultTemplate/);
      assert.match(html, /--premium-accent:#dc2626/);
      assert.match(html, /--badge-special:#abcdef/);
      assert.match(html, /--button-radius:18px/);
      assert.match(html, /--font-display:Roboto/);
      assert.match(html, /Instalar aplicativo/);
    }
  }
});
test('custom branding keeps its profile and uploaded assets take priority', () => {
  for (const settings of [{ theme: 'dark', primary_color: '#2563eb' }, { theme: 'white', primary_color: '#123456' }]) {
    const custom = render({ ...menu, public_settings: settings });
    assert.doesNotMatch(custom, /defaultTemplate|logoFallback/);
    assert.match(custom, new RegExp(`--premium-accent:${settings.primary_color}`));
  }
  const html = render({ ...menu, public_settings: { ...menu.public_settings, logo_url: '/logo.png', cover_image_url: '/cover.png' } });
  assert.match(html, /data-has-cover="true"/);
  assert.match(html, /src="\/cover.png"/);
  assert.match(html, /src="\/logo.png"/);
  assert.doesNotMatch(html, /logoFallback/);
});
test('fallback layout fits 320–520px in Chromium even inside a wider desktop page', { skip: !fs.existsSync('/usr/bin/chromium') }, async () => {
  const css = fs.readFileSync(path.join(root, 'styles/menu-tokens.css'), 'utf8') + fs.readFileSync(path.join(root, 'components/PublicMenu/PublicMenu.module.css'), 'utf8');
  const variants = [render(), render({ ...menu, categories: [] }), render(menu, { enableCart: false, forcedTheme: 'white', hideThemeToggle: true })];
  const frames = [320, 360, 390, 430, 520].flatMap(width => variants.map(markup => {
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
        theme: d.querySelector('main').dataset.theme,
        installVisible: getComputedStyle(d.querySelector('.installSection')).display,
        overlay: getComputedStyle(d.querySelector('.heroOverlay')).display,
        ratio: image ? image.clientWidth / image.clientHeight : null,
      };
    }));
    assert.equal(results.length, 15);
    for (const result of results) {
      assert.ok(result.scroll <= result.width, JSON.stringify(result));
      assert.equal(result.height, 330);
      assert.equal(result.overlay, 'block');
      assert.notEqual(result.installVisible, 'none');
      if (result.ratio) assert.ok(Math.abs(result.ratio - 4 / 3) < .03);
    }
  } finally {
    if (browser) await browser.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('install card button follows the restaurant color in light and dark modes', { skip: !fs.existsSync('/usr/bin/chromium') }, async () => {
  const css = fs.readFileSync(path.join(root, 'styles/menu-tokens.css'), 'utf8') + fs.readFileSync(path.join(root, 'components/PublicMenu/PublicMenu.module.css'), 'utf8');
  const variants = [
    { color: '#eab308', theme: 'white', foreground: 'rgb(23, 17, 10)' },
    { color: '#123456', theme: 'dark', foreground: 'rgb(255, 255, 255)' },
  ];
  const dir = fs.mkdtempSync('/tmp/public-menu-install-');
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
      headless: true, userDataDir: `${dir}/browser`,
      args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking'],
      env: { ...process.env, XDG_CACHE_HOME: dir, XDG_CONFIG_HOME: dir },
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 390, height: 844 });
    for (const variant of variants) {
      const markup = render({ ...menu, public_settings: { ...menu.public_settings, primary_color: variant.color, theme: variant.theme } }, { forcedTheme: variant.theme });
      await page.setContent(`<style>*{box-sizing:border-box}body{margin:0}${css}</style>${markup}`);
      const result = await page.evaluate(() => {
        const card = document.querySelector('.installSection');
        const button = card.querySelector('.installButton');
        return {
          background: getComputedStyle(button).backgroundColor,
          foreground: getComputedStyle(button).color,
          cardWidth: card.getBoundingClientRect().width,
          buttonWidth: button.getBoundingClientRect().width,
          pageWidth: document.documentElement.scrollWidth,
        };
      });
      assert.equal(result.background, `rgb(${parseInt(variant.color.slice(1, 3), 16)}, ${parseInt(variant.color.slice(3, 5), 16)}, ${parseInt(variant.color.slice(5, 7), 16)})`);
      assert.equal(result.foreground, variant.foreground);
      assert.ok(result.buttonWidth >= result.cardWidth - 32, JSON.stringify(result));
      assert.ok(result.pageWidth <= 390, JSON.stringify(result));
    }
    await page.setViewport({ width: 800, height: 844 });
    await page.setContent(`<style>*{box-sizing:border-box}body{margin:0}${css}</style>${render(menu, { forcedTheme: 'white' })}`);
    assert.equal(await page.$eval('.installSection', element => getComputedStyle(element).display), 'none');
  } finally {
    if (browser) await browser.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
