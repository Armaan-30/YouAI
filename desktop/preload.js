const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('desktop',{
 getVoices:()=>ipcRenderer.invoke('voices'),
 speak:(text,options)=>ipcRenderer.invoke('speak',text,options),
 stopSpeech:()=>ipcRenderer.send('stop-speech'),
 setListening:value=>ipcRenderer.send('listening-state',Boolean(value)),
 choosePath:kind=>ipcRenderer.invoke('choose-path',kind),
 onActivate:callback=>ipcRenderer.on('activate',()=>callback())
});
