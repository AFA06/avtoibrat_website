const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.PREVIEW_URL || 'http://127.0.0.1:8000/uz/');
  await page.waitForFunction(()=>document.querySelector('.pass')?.driveFrame?.());
  assert((await page.locator('.drive-view').getAttribute('data-car')).includes('gentra'));
  const state=()=>page.locator('.pass').evaluate(e=>e.driveFrame());
  assert.equal((await state()).wheels,4);
  await page.locator('[data-seek=".43"]').click();
  await page.waitForFunction(()=>document.querySelector('.pass').driveFrame().braking);
  await page.locator('[data-seek=".96"]').click();
  await page.locator('.game-launch').click();
  await page.keyboard.down('a');
  await page.waitForFunction(()=>document.querySelector('.pass').driveFrame().indicator==='L');
  await page.waitForFunction(()=>document.querySelector('.pass').driveFrame().blink);
  await page.waitForFunction(()=>!document.querySelector('.pass').driveFrame().blink);
  await page.keyboard.up('a');await page.keyboard.down('d');
  await page.waitForFunction(()=>document.querySelector('.pass').driveFrame().indicator==='R');
  await page.keyboard.up('d');
  await page.waitForFunction(()=>document.querySelector('.pass').driveFrame().indicator===null);
  await page.keyboard.press('Escape');
  await page.locator('[data-seek="0"]').click();
  await page.waitForFunction(()=>document.querySelector('.pass').driveFrame().progress<.001);
  await page.screenshot({path:'design-review/drive/gentra-final.jpg'});
  assert.deepEqual(errors,[]);
  console.log('Gentra: four wheels, stop brake lights, left/right signals, timed blinking, auto-cancel and scene restore passed.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
