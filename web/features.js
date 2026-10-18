/* Desktop feature controls. Content is always rendered as text, never HTML. */
window.selectedDocuments=new Set();
let pendingAction=null;
const guard=fn=>async event=>{event?.preventDefault();try{await fn(event);}catch(error){showError(error.message);}};
window.refreshFeatures=async()=>{
  const {memories}=await api('/api/memories');$('memories').replaceChildren();
  for(const memory of memories){
    const row=document.createElement('div');row.className='note';
    const text=document.createElement('span');text.textContent=memory.content;
    const edit=document.createElement('button');edit.textContent='Edit';edit.className='quiet';edit.onclick=guard(async()=>{
      const content=prompt('Edit this approved memory:',memory.content);if(content===null)return;
      await api('/api/memories/'+memory.id,{...json({content,approved:true}),method:'PUT'});await refreshFeatures();
    });
    const remove=document.createElement('button');remove.textContent='Forget';remove.className='quiet';remove.onclick=guard(async()=>{
      if(!confirm('Forget this memory? Past conversation text remains until you clear history.'))return;
      await api('/api/memories/'+memory.id,{method:'DELETE'});await refreshFeatures();
    });row.append(text,edit,remove);$('memories').append(row);
  }
  if(window.YouAIPlatform?.native || window.cloudMode)return;
  const {permissions}=await api('/api/desktop/permissions');$('permissions').replaceChildren();$('action-location').replaceChildren();
  for(const entry of permissions){
    const option=document.createElement('option');option.value=entry.id;option.textContent=entry.kind+': '+entry.path;$('action-location').append(option);
    const row=document.createElement('div');row.className='note';row.textContent=entry.path+(entry.watch_status?' · '+entry.watch_status:'');
    const remove=document.createElement('button');remove.textContent='Revoke';remove.className='quiet';remove.onclick=guard(async()=>{await api('/api/desktop/permissions/'+entry.id,{method:'DELETE'});await refreshFeatures();});row.append(remove);$('permissions').append(row);
  }
};
$('memory-form').onsubmit=guard(async()=>{
  await api('/api/memories',json({content:$('memory-text').value,approved:true}));$('memory-text').value='';await refreshFeatures();
});
$('permission-form').onsubmit=guard(async()=>{
  const path=$('permission-path').value;if(!confirm('Allow YouAI to use this '+$('permission-kind').value+'?\n'+path))return;
  await api('/api/desktop/permissions',json({kind:$('permission-kind').value,path,approved:true}));await refreshFeatures();
});
$('action-form').onsubmit=guard(async()=>{
  pendingAction=null;$('action-confirm').hidden=true;
  const result=await api('/api/desktop/preview',json({permission_id:Number($('action-location').value),operation:$('action-operation').value,name:$('action-name').value,content:$('action-content').value}));
  $('action-result').textContent=result.preview || (result.results.length?result.results.join('\n'):'No matching filenames in the first 10,000 files searched.');
  pendingAction=result.token;$('action-confirm').hidden=!pendingAction;
});
$('action-confirm').onclick=guard(async()=>{
  if(!pendingAction)return;const token=pendingAction;pendingAction=null;$('action-confirm').hidden=true;
  const result=await api('/api/desktop/confirm',json({token,approved:true}));$('action-result').textContent=result.message;
});
$('history-search-form').onsubmit=guard(async()=>{
  const result=await api('/api/history/search?q='+encodeURIComponent($('history-query').value));$('history-results').replaceChildren();
  for(const item of result.messages){const line=document.createElement('p');line.textContent=item.role+': '+item.content;$('history-results').append(line);}
});
let documentSearchTimer;
$('document-search').oninput=()=>{clearTimeout(documentSearchTimer);documentSearchTimer=setTimeout(()=>refreshDocuments().catch(e=>showError(e.message)),250);};
$('use-web').onchange=()=>{if($('use-web').checked){$('use-documents').checked=false;showError('Online mode: your question will be sent to external search (DuckDuckGo by default). Documents and personal memories are not sent.');}else showError('');};
$('use-documents').onchange=()=>{if($('use-documents').checked)$('use-web').checked=false;};
async function populateVoices(){
  const selected=localStorage.getItem('youai-voice')||'';$('voice-choice').replaceChildren(new Option('Automatic (Zira preferred)',''));
  const voices=window.desktop?.getVoices?await desktop.getVoices().catch(()=>[]):speechSynthesis.getVoices();
  for(const voice of voices.filter(v=>window.cloudMode || v.localService))$('voice-choice').add(new Option(voice.name+' · '+voice.lang,voice.voiceURI));
  $('voice-choice').value=selected;
  if(selected && !voices.some(v=>v.voiceURI===selected))localStorage.removeItem('youai-voice');
}
speechSynthesis.addEventListener('voiceschanged',populateVoices);populateVoices();
$('voice-choice').onchange=()=>localStorage.setItem('youai-voice',$('voice-choice').value);
$('voice-rate').value=localStorage.getItem('youai-rate')||'0.9';$('voice-rate').onchange=()=>localStorage.setItem('youai-rate',$('voice-rate').value);
$('pause-duration').value=localStorage.getItem('youai-pause')||'1100';$('pause-duration').onchange=()=>localStorage.setItem('youai-pause',$('pause-duration').value);
$('voice-preview').onclick=guard(async()=>{await stopAll();await say("Hi, I'm You. Take your time. I'm here to help.",generation);idle();});
if(window.desktop){
  $('notifications').hidden=true;
  $('choose-path').hidden=false;$('choose-path').onclick=guard(async()=>{const path=await desktop.choosePath($('permission-kind').value);if(path)$('permission-path').value=path;});
  desktop.onActivate(async()=>{await stopAll();await record();});
  document.querySelector('footer>span:last-child').textContent='YOU / WINDOWS DESKTOP';
}

$('speech-language').value=localStorage.getItem('youai-language')||'auto';$('speech-language').onchange=()=>localStorage.setItem('youai-language',$('speech-language').value);
$('wake-stability').value=localStorage.getItem('youai-stability')||'2';$('wake-stability').onchange=async()=>{localStorage.setItem('youai-stability',$('wake-stability').value);await stopAll();idle();};

$('barge-in').onchange=()=>{if(!$('barge-in').checked){interruptionCapture?.close();interruptionCapture=null;}};

if(window.desktop){$('background-wake-label').hidden=false;$('background-wake').onchange=async()=>{if(!$('background-wake').checked&&document.hidden)await stopAll();};}

window.handleLaptopCommand=async text=>{
  if(window.YouAIPlatform?.native)return false;
  const open=text.match(/^open (?:app )?(.+?)[.!]?$/i);
  const find=text.match(/^(?:find|search) files (?:named|containing) (.+)/i);
  if(!open&&!find)return false;
  if(window.cloudMode){showError('Laptop actions require the Windows desktop app.');return true;}
  await stopAll();if(!$('panel').open)$('panel').showModal();
  await refreshFeatures();
  if(open){
    const {permissions}=await api('/api/desktop/permissions');
    const requested=open[1].trim().toLowerCase().replace(/\.exe$/,'');
    const matches=permissions.filter(p=>p.kind==='app' && p.path.split(/[\\/]/).pop().replace(/\.exe$/i,'').toLowerCase()===requested);
    if(matches.length!==1){showError('Approve this application in Laptop actions first. Say its executable name, for example “open notepad”.');return true;}
    $('action-location').value=matches[0].id;$('action-operation').value='open';
  }else{
    $('action-operation').value='search';$('action-name').value=find[1];
    if(!$('action-location').value){showError('Approve and select a folder in Laptop actions first.');return true;}
  }
  await $('action-form').onsubmit(new Event('submit'));$('action-result').scrollIntoView({block:'center'});return true;
};
