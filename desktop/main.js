const {app,BrowserWindow,Tray,Menu,nativeImage,globalShortcut,Notification,ipcMain,dialog,shell,powerMonitor}=require('electron');
const {spawn,execFile,execFileSync}=require('node:child_process');
const fs=require('node:fs');const path=require('node:path');
const port=Number(process.env.YOUAI_DESKTOP_PORT||8765);if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid port');
const origin='http://127.0.0.1:'+port;let win,tray,backend,quitting=false,polling=false;const notified=new Set();let speechProcess;
app.setAppUserModelId('com.youai.desktop');
if(process.env.YOUAI_DESKTOP_TEST==='1')app.setPath('userData',path.join(app.getPath('temp'),'youai-desktop-test'));
if(!app.requestSingleInstanceLock()){app.quit();}else{
app.on('second-instance',()=>show());
app.whenReady().then(start).catch(error=>{dialog.showErrorBox('YouAI could not start',error.message);app.quit();});
}
function show(){if(win){win.show();win.focus();}}
async function request(route,options={}){
 const response=await fetch(origin+route,{...options,headers:{'X-YouAI':'1',...options.headers},signal:AbortSignal.timeout(5000)});
 if(!response.ok)throw new Error('YouAI server: '+response.status);return response.json();
}
function icon(){const size=32,data=Buffer.alloc(size*size*4);for(let y=0;y<size;y++)for(let x=0;x<size;x++){let i=(y*size+x)*4;let circle=(x-16)**2+(y-16)**2<210;let mic=x>=13&&x<=18&&y>=7&&y<=21;data[i]=mic?245:65;data[i+1]=mic?245:105;data[i+2]=mic?245:86;data[i+3]=circle?255:0;}return nativeImage.createFromBitmap(data,{width:size,height:size});}
async function start(){
 let root, python;
 if(app.isPackaged && (process.env.YOUAI_DESKTOP_TEST!=='1'||process.env.YOUAI_TEST_BUNDLED==='1')){
  root=path.join(process.resourcesPath,'backend');
  python=await require('./bootstrap')(root,process.env.YOUAI_TEST_RUNTIME||path.join(app.getPath('userData'),'runtime'));
 }else{
  root=process.env.YOUAI_PROJECT_ROOT||path.resolve(__dirname,'..');
  if(app.isPackaged)root=process.env.YOUAI_PROJECT_ROOT||process.cwd();
  python=path.join(root,'.venv','Scripts','python.exe');
 }
 if(!fs.existsSync(python))throw new Error('Python environment missing. Run setup.ps1 first.');
 try{await fetch('http://127.0.0.1:11434/api/tags',{signal:AbortSignal.timeout(1500)});}catch{
  const ollama=path.join(process.env.LOCALAPPDATA,'Programs','Ollama','ollama.exe');
  if(fs.existsSync(ollama))spawn(ollama,['serve'],{windowsHide:true,stdio:'ignore'}).on('error',()=>{});
 }
 try{await request('/api/status');}catch{
  backend=spawn(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port)],{cwd:root,windowsHide:true,stdio:'ignore'});
  backend.on('error',e=>dialog.showErrorBox('Backend failed',e.message));
  let ready=false;for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,500));try{await request('/api/status');ready=true;break;}catch{}}
  if(!ready)throw new Error('Backend did not start. Run start.ps1 to inspect the problem.');
 }
 win=new BrowserWindow({show:process.env.YOUAI_DESKTOP_TEST!=="1",width:960,height:820,minWidth:390,minHeight:600,icon:icon(),webPreferences:{preload:path.join(__dirname,'preload.js'),contextIsolation:true,nodeIntegration:false,sandbox:true,backgroundThrottling:false}});
 win.setMenuBarVisibility(false);
 win.webContents.session.setPermissionRequestHandler((contents,permission,callback,details)=>callback(contents===win.webContents&&details.requestingUrl.startsWith(origin+'/')&&permission==='media'&&!details.mediaTypes?.includes('video')));
 win.webContents.session.setPermissionCheckHandler((contents,permission,requestingOrigin)=>contents===win.webContents&&requestingOrigin===origin&&permission==='media');
 win.webContents.on('will-navigate',(event,url)=>{if(new URL(url).origin!==origin)event.preventDefault();});
 win.webContents.setWindowOpenHandler(({url})=>{if(url.startsWith('https://'))dialog.showMessageBox(win,{type:'question',message:'Open this source in your browser?',detail:url,buttons:['Cancel','Open']}).then(r=>{if(r.response===1)shell.openExternal(url);});return {action:'deny'};});
 win.on('close',event=>{if(!quitting){event.preventDefault();win.hide();}});
 await win.loadURL(origin);
 tray=new Tray(icon());tray.setToolTip('YouAI • Ctrl+Alt+Space to talk');tray.setContextMenu(Menu.buildFromTemplate([
  {label:'Open YouAI',click:show},{label:'Start with Windows',type:'checkbox',checked:app.getLoginItemSettings().openAtLogin,click:item=>app.setLoginItemSettings({openAtLogin:item.checked})},
  {label:'Quit YouAI',click:()=>{quitting=true;app.quit();}}
 ]));tray.on('double-click',show);
 const registered=globalShortcut.register('Control+Alt+Space',()=>{show();win.webContents.send('activate');});
 if(!registered)dialog.showMessageBox(win,{message:'Ctrl+Alt+Space is already in use. Open YouAI from the tray instead.'});
 setInterval(pollReminders,3000);powerMonitor.on('resume',pollReminders);pollReminders();
}
async function pollReminders(){
 if(polling)return;polling=true;
 try{
  const {reminders}=await request('/api/desktop/alerts');
  for(const r of reminders){
   if(notified.has(r.id))continue;
   if(Notification.isSupported()){
    const notice=new Notification({title:'YouAI reminder',body:r.content,timeoutType:'never'});
    notified.add(r.id);
    notice.on('show',()=>request('/api/desktop/alerts/'+r.id,{method:'POST'}).catch(()=>notified.delete(r.id)));
    notice.on('failed',()=>notified.delete(r.id));notice.on('click',show);notice.show();
   }
  }
 }catch{}finally{polling=false;}
}
function trusted(event){return win && event.sender===win.webContents && new URL(event.senderFrame.url).origin===origin;}
function powershell(script){return ['-NoProfile','-NonInteractive','-EncodedCommand',Buffer.from(script,'utf16le').toString('base64')];}
ipcMain.handle('voices',async event=>{
 if(!trusted(event))throw new Error('Untrusted page');
 const script="Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; @($s.GetInstalledVoices() | Where-Object Enabled | ForEach-Object { @{name=$_.VoiceInfo.Name; lang=$_.VoiceInfo.Culture.Name; voiceURI=$_.VoiceInfo.Name; localService=$true} }) | ConvertTo-Json -Compress; $s.Dispose()";
 return new Promise((resolve,reject)=>execFile('powershell.exe',powershell(script),{windowsHide:true,timeout:10000},(error,stdout)=>{if(error)return reject(new Error('Windows voices unavailable'));try{const result=JSON.parse(stdout);resolve(Array.isArray(result)?result:[result]);}catch{resolve([]);}}));
});
ipcMain.handle('speak',async(event,text,options)=>{
 if(!trusted(event)||typeof text!=='string'||text.length>8000)throw new Error('Invalid speech request');
 speechProcess?.kill();
 const payload=Buffer.from(JSON.stringify({text,voice:String(options?.voice||''),rate:Math.max(-4,Math.min(4,Math.round((Number(options?.rate)||.9)*10-10)))}),'utf8').toString('base64');
 const script="Add-Type -AssemblyName System.Speech; $v=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+payload+"')) | ConvertFrom-Json; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; if($v.voice){$s.SelectVoice($v.voice)} else {$voice=$s.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Name -match 'Zira|Heera'} | Select-Object -First 1; if($voice){$s.SelectVoice($voice.VoiceInfo.Name)}}; $s.Rate=$v.rate; $s.Volume=90; $s.Speak($v.text); $s.Dispose()";
 return new Promise((resolve,reject)=>{const child=spawn('powershell.exe',powershell(script),{windowsHide:true,stdio:'ignore'});speechProcess=child;child.once('error',()=>reject(new Error('Windows speech could not start')));child.once('exit',code=>{if(speechProcess===child)speechProcess=null;if(code && !child.killed)reject(new Error('Windows speech failed; choose another installed voice'));else resolve();});});
});
ipcMain.on('stop-speech',event=>{if(trusted(event)){speechProcess?.kill();speechProcess=null;}});
ipcMain.on('listening-state',(event,listening)=>{
 if(win && event.sender===win.webContents && new URL(event.senderFrame.url).origin===origin && tray)
  tray.setToolTip(listening?'YouAI • Microphone active (Hey You/listening)':'YouAI • Microphone off • Ctrl+Alt+Space');
});
ipcMain.handle('choose-path',async(event,kind)=>{
 if(event.sender!==win.webContents||new URL(event.senderFrame.url).origin!==origin)throw new Error('Untrusted page');
 if(!['app','folder'].includes(kind))throw new Error('Invalid type');
 const result=await dialog.showOpenDialog(win,{properties:kind==='folder'?['openDirectory']:['openFile'],...(kind==='app'?{filters:[{name:'Applications',extensions:['exe']}]}:{})});
 return result.canceled?null:result.filePaths[0];
});
app.on('window-all-closed',()=>{});
app.on('before-quit',()=>{quitting=true;});
app.on('will-quit',()=>{speechProcess?.kill();globalShortcut.unregisterAll();if(backend?.pid){try{execFileSync('taskkill',['/PID',String(backend.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});}catch{}}});
