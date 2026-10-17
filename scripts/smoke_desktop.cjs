const { _electron: electron }=require('@playwright/test');
const path=require('node:path');
(async()=>{
 const app=await electron.launch({executablePath:process.env.YOUAI_TEST_EXE||path.resolve('dist/win-unpacked/YouAI.exe'),env:{...process.env,YOUAI_PROJECT_ROOT:process.cwd(),YOUAI_DESKTOP_TEST:'1',YOUAI_DESKTOP_PORT:'8767',YOUAI_DATA_DIR:path.resolve('.runtime/desktop-smoke'),YOUAI_PRELOAD:'0'},timeout:45000});
 try{
  const page=await app.firstWindow();
  await page.waitForURL('http://127.0.0.1:8767/');
  await page.waitForFunction(()=>Boolean(document.getElementById('open-panel')?.onclick));
  await page.locator('#open-panel').evaluate(button=>button.click());await page.locator('#memory-form').waitFor();
  const result=await app.evaluate(({globalShortcut,BrowserWindow,Notification})=>({shortcut:globalShortcut.isRegistered('Control+Alt+Space'),windows:BrowserWindow.getAllWindows().length,notifications:Notification.isSupported()}));
  if(!result.shortcut||result.windows!==1)throw new Error('Desktop initialization failed');
  if(!await page.evaluate(()=>Boolean(window.desktop?.choosePath)))throw new Error('Desktop bridge missing');
  const voices=await page.evaluate(()=>desktop.getVoices());if(!voices.length)throw new Error('No native Windows voices found');console.log('Installed Windows voices:',voices.map(v=>v.name).join(', '));
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].show());
  await page.screenshot({path:'.runtime/desktop-smoke.png'});console.log(JSON.stringify(result));
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].close());
  const remains=await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().length);if(remains!==1)throw new Error('Close did not retain tray app');
  console.log('Desktop window, bridge, shortcut, tray-close behavior passed.');
  require('node:child_process').execFileSync(path.resolve('.venv/Scripts/python.exe'),['-c',"import sqlite3,time; db=sqlite3.connect('.runtime/desktop-smoke/youai.sqlite3'); db.execute(\"INSERT INTO reminders(content,due_at) VALUES ('YouAI release notification test',?)\",(time.time()-1,)); db.commit()"],{windowsHide:true});
  let delivered=false;
  for(let i=0;i<20;i++){
   await new Promise(resolve=>setTimeout(resolve,1000));
   const pending=await page.evaluate(async()=> (await (await fetch('/api/desktop/alerts')).json()).reminders);
   if(!pending.some(r=>r.content==='YouAI release notification test')){delivered=true;break;}
  }
  if(!delivered)throw new Error('Native notification show acknowledgment did not arrive while window was hidden');
  console.log('Native reminder show event acknowledged while window hidden. Human visibility still needs confirmation.');
 }finally{await app.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
