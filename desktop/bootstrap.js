const {BrowserWindow}=require('electron');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
module.exports=async function bootstrap(root,runtime){
 const python=path.join(runtime,'.venv','Scripts','python.exe');
 const ready=path.join(runtime,'ready.txt');
 if(fs.existsSync(python)&&fs.existsSync(ready)&&fs.readFileSync(ready,'utf8').trim()==='0.4.0')return python;
 fs.mkdirSync(runtime,{recursive:true});
 const log=fs.createWriteStream(path.join(runtime,'setup.log'),{flags:'a'});
 const window=new BrowserWindow({width:620,height:320,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}});
 await window.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent('<html><body style="font:18px system-ui;padding:30px;background:#eef2ec;color:#23382b"><h2>Setting up YouAI</h2><p>Installing Python, Ollama and local AI models. First setup needs internet and several GB of free space.</p><p>You can close this window to cancel and retry next time.</p><p id="status" role="status">Starting downloads…</p></body></html>'));
 return new Promise((resolve,reject)=>{
  let done=false;
  const child=spawn('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(root,'scripts','bootstrap_windows.ps1'),'-BackendRoot',root,'-RuntimeRoot',runtime],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  const output=data=>{log.write(data);if(!window.isDestroyed())window.webContents.executeJavaScript('document.getElementById("status").textContent='+JSON.stringify(data.toString().slice(-400))).catch(()=>{});};
  child.stdout.on('data',output);child.stderr.on('data',output);
  window.on('closed',()=>{if(!done){spawn('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'}).on('error',()=>{});}});
  const finish=error=>{if(done)return;done=true;log.end();if(!window.isDestroyed())window.destroy();error?reject(error):resolve(python);};
  child.once('error',()=>finish(new Error('Could not start setup. See '+path.join(runtime,'setup.log'))));
  child.once('exit',code=>finish(code===0?null:new Error('Setup did not finish. Restart to retry. Log: '+path.join(runtime,'setup.log'))));
 });
};
