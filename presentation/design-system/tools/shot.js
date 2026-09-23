const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' }).catch(async () => chromium.launch());
  const files = process.argv.slice(2);
  process.chdir(require('path').join(__dirname, '..'));
  fs.mkdirSync('shots', { recursive: true });
  for (const f of files) {
    const src = fs.readFileSync('test/' + f, 'utf8');
    const m = /width=(\d+)/.exec(src.split('\n')[0]); const hm = /height=(\d+)/.exec(src.split('\n')[0]);
    const p = await b.newPage({ viewport: { width: m ? +m[1] : (f.startsWith('Cover') ? 960 : 900), height: hm ? +hm[1] : 400 } });
    const errs = [];
    p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await p.goto('file://' + process.cwd() + '/test/' + f);
    await p.waitForTimeout(300);
    const sh = await p.evaluate(() => (document.getElementById('root')||document.body).scrollHeight);
    await p.screenshot({ path: 'shots/' + f.replace('.html', '.png'), fullPage: true });
    console.log(f, 'rootH=' + sh, errs.filter(e => !/fonts.googleapis|ERR_/.test(e)).join(' | '));
    await p.close();
  }
  await b.close();
})();
