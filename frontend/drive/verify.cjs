const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const url = process.env.PREVIEW_URL || 'http://127.0.0.1:8000/uz/';
const output = path.resolve(__dirname, '../../design-review/drive');
const stops = [0, .1, .25, .4, .6, .8, 1];

async function capture(browser, mobile) {
  const label = mobile ? 'mobile' : 'desktop';
  const viewport = mobile ? {width:390,height:844} : {width:1440,height:900};
  const recordDir = mobile ? null : fs.mkdtempSync(path.join(os.tmpdir(),'avtoibrat-film-'));
  const context = await browser.newContext({viewport,
    ...(recordDir ? {recordVideo:{dir:recordDir,size:viewport}} : {})});
  const page = await context.newPage();
  const video = page.video();
  const result = {viewport,forward:[],reverse:[],errors:[],warnings:[],assets:[]};
  page.on('pageerror', error=>result.errors.push(error.message));
  page.on('console', message=>{
    if (message.type()==='error') result.errors.push(message.text());
    if (message.type()==='warning') result.warnings.push(message.text());
  });
  page.on('response', response=>{
    if (response.status()>=400) result.errors.push(response.status()+' '+response.url());
    if (response.url().includes('/drive/')) result.assets.push([response.status(),response.url()]);
  });
  async function travel(progress, direction) {
    await page.evaluate(async ({progress,mobile})=>{
      const t = ScrollTrigger.getById('drive');
      const target = Math.round(t.start+progress*(t.end-t.start));
      const start = scrollY, then = performance.now();
      await new Promise(resolve=>{
        function tick(now) {
          const x = Math.min(1,(now-then)/(mobile ? 500 : 1750));
          scrollTo({top:start+(target-start)*x*x*(3-2*x),behavior:'instant'});
          if (x<1) requestAnimationFrame(tick); else resolve();
        }
        requestAnimationFrame(tick);
      });
    },{progress,mobile});
    await page.waitForFunction(p=>{
      const frame=document.querySelector('.pass').driveFrame();
      const trigger=ScrollTrigger.getById('drive');
      return Math.abs(frame.progress-p)<.0006 && Math.abs(frame.progress-trigger.progress)<.000002;
    },progress);
    const state = await page.locator('.pass').evaluate(el=>el.driveFrame());
    result[direction].push(state);
    const name = [label,direction,String(progress*100).padStart(3,'0')].join('-');
    await page.screenshot({path:path.join(output,name+'.jpg'),quality:88});
  }
  try {
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelector('.pass')?.driveFrame?.(),null,{timeout:60000});
    await page.waitForFunction(()=>ScrollTrigger.getById('drive').animation.getChildren()[0].targets()[0].opening>.999);
    await page.evaluate(()=>{document.documentElement.style.scrollBehavior='auto'});
    for (const progress of stops) await travel(progress,'forward');
    await page.evaluate(()=>scrollTo({top:ScrollTrigger.getById('drive').end+innerHeight*.75,behavior:'instant'}));
    await page.waitForFunction(()=>document.querySelector('#courses').getBoundingClientRect().top<innerHeight*.65);
    for (const progress of [...stops].reverse()) await travel(progress,'reverse');
    for (const [index,forward] of result.forward.entries()) {
      const reverse = result.reverse[stops.length-1-index];
      const delta = key=>Math.hypot(...forward[key].map((v,i)=>v-reverse[key][i]));
      assert(delta('position')<.35 && delta('camera')<.5, label+' at '+stops[index]+': position delta '+delta('position')+', camera delta '+delta('camera'));
      assert(Math.abs(forward.building-reverse.building)<.025);
      assert.equal(forward.signal,reverse.signal);
    }
    const f = result.forward;
    assert(f[0].building<.01 && f[2].building>.9 && f.at(-1).building<.01);
    assert(f.at(-1).training>.99 && Math.abs(f[4].steer)>.005);
    assert(f.at(-1).wheel>f[2].wheel+100);
    await page.locator('.pass-layout a[href="#apply"]').click();
    assert(await page.locator('[name=csrfmiddlewaretoken]').count());
    assert.deepEqual(result.errors,[]);
    result.warnings=[...new Set(result.warnings)];
    fs.writeFileSync(path.join(output,label+'-states.json'),JSON.stringify(result,null,2));
  } finally {await context.close()}
  if (video) {
    await video.saveAs(path.join(output,'scroll-drive.webm'));
    await video.delete();
    fs.rmdirSync(recordDir);
  }
  console.log(label+' forward and reverse passed');
}

(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({channel:'chrome',args:['--enable-unsafe-swiftshader']});
  try {await capture(browser,false);await capture(browser,true)}
  finally {await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
