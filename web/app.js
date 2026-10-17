const $ = (id) => document.getElementById(id);
let interruptionCapture = null;
let state = "idle", generation = 0, recording = null, requestAbort = null;
let turnId = null, wakeTimer = null, lastAnswer = "", ready = false, speechFinish = null;
const labels = {idle:"Tap to talk", starting:"Opening your microphone", armed:"Listening for “Hey You”", listening:"I’m listening", transcribing:"Finding your words", thinking:"Thinking with you", speaking:"Speaking"};
const hints = {idle:"Your own space to think out loud.", starting:"Just a moment…", armed:"Say “Hey You”, followed by your request.", listening:"Tap to finish, or pause when you’re done.", transcribing:"Turning your voice into words, here on your laptop.", thinking:"Tap the circle to stop.", speaking:"Tap the circle to interrupt."};
function setState(next) {
  window.desktop?.setListening?.(["starting","armed","listening"].includes(next) || Boolean(interruptionCapture));
  state = next; $("orb").dataset.state = next;
  $("state").textContent = labels[next]; $("hint").textContent = hints[next];
  $("orb").setAttribute("aria-label", next === "idle" || next === "armed" ? "Start listening" : "Stop");
}
function showError(message) { $("error").hidden = !message; $("error").textContent = message || ""; }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"X-YouAI":"1", ...options.headers}});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "That request could not be completed.");
  return data;
}
function json(value) { return {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(value)}; }
async function refresh() {
  try {
    const result = await api("/api/status");
    ready = result.llm_ready;
    const onlineChat=result.provider==='groq', onlineSpeech=result.speech_provider==='groq';
    $("connection").textContent = ready ? (onlineChat ? 'Groq connected · '+result.model : 'Local model connected') : (onlineChat ? 'Groq unavailable' : 'Local model unavailable');
    const notice=$('provider-notice');notice.hidden=!(onlineChat||onlineSpeech);
    notice.textContent=[onlineChat?'Online chat: messages, recent conversation, approved memories and document passages used for answers/summaries are sent to Groq.':'',onlineSpeech?'Voice requests are uploaded to Groq for transcription. Wake listening and spoken playback stay local.':''].filter(Boolean).join(' ');
    $('processing-location').textContent=onlineChat||onlineSpeech?'Groq online processing · storage on your laptop':'On your laptop. In your control.';
    hints.transcribing=onlineSpeech?'Transcribing your voice through Groq.':'Turning your voice into words, here on your laptop.';
    if (!ready) showError(result.error);
    else showError("");
  } catch { $("connection").textContent = "App disconnected"; showError("The local app is offline. Run start.ps1, then reload this page."); }
}
async function refreshHistory() {
  const [history, notes] = await Promise.all([api("/api/history"), api("/api/notes")]);
  $("history").replaceChildren();
  for (const item of history.messages) {
    const block = document.createElement("div"); block.className = "message";
    const who = document.createElement("strong"); who.textContent = item.role === "user" ? "You said" : "YouAI";
    block.append(who, document.createTextNode(item.content)); $("history").append(block);
    if(item.sources?.length) renderSources(item.sources,block);
  }
  $("notes").replaceChildren();
  for (const item of notes.notes) {
    const block = document.createElement("div"); block.className = "note";
    block.textContent = item.content; $("notes").append(block);
  }
}
function releaseRecorder() {
  recording?.close(); recording = null;
}
async function stopAll() {
  generation++;
  interruptionCapture?.close(); interruptionCapture=null;
  clearTimeout(wakeTimer); wakeTimer = null;
  releaseRecorder();
  speechFinish?.();
  speechSynthesis.cancel(); window.desktop?.stopSpeech?.();
  const pending = turnId; turnId = null;
  if (pending) await api("/api/cancel/" + pending, {method:"POST"}).catch(() => {});
  requestAbort?.abort(); requestAbort = null;
  setState("idle");
}
function idle() {
  setState("idle");
  if ($("wake").checked && (!document.hidden || (window.desktop && $("background-wake")?.checked))) {
    setState("armed");
    clearTimeout(wakeTimer);
    wakeTimer = setTimeout(() => record(true), 200);
  }
}
async function say(text, ticket) {
  if (!$("speak").checked) return;
  if ($("barge-in")?.checked && !interruptionCapture) await startInterruption();
  text=text.replace(/\[S\d+\]/g,"");
  if(window.desktop?.speak){
    if(ticket!==generation)return;setState("speaking");
    try{await desktop.speak(text,{voice:localStorage.getItem("youai-voice")||"",rate:Number(localStorage.getItem("youai-rate")||.9)});}catch(error){if(ticket===generation)showError(error.message);}
    return;
  }
  if(window.YouAIPlatform?.native) {
    if(ticket!==generation) return;
    setState("speaking");
    try {await YouAIPlatform.speak(text);} catch(error){if(ticket===generation) showError(error.message);}
    return;
  }
  // Deliberately exclude browser/network voices.
  // Windows can publish its voices after the page has already loaded.
  if (!speechSynthesis.getVoices().length) {
    await new Promise(resolve => {
      const finish = () => {
        clearTimeout(timer);
        speechSynthesis.removeEventListener("voiceschanged", finish);
        resolve();
      };
      const timer = setTimeout(finish, 1500);
      speechSynthesis.addEventListener("voiceschanged", finish);
    });
  }
  if (ticket !== generation || !$("speak").checked) return;
  const voices = speechSynthesis.getVoices().filter(v => v.localService);
  if (!voices.length) { showError("No local speech voice is available. Install a Windows speech voice or use the text response."); return; }
  // These installed Windows voices are female; the browser has no gender field.
  const voice = voices.find(v => v.voiceURI === localStorage.getItem("youai-voice")) || voices.find(v => /\bZira\b/i.test(v.name))
    || voices.find(v => /\bHeera\b/i.test(v.name))
    || voices.find(v => v.lang.startsWith(navigator.language.split("-")[0]))
    || voices.find(v => v.lang.startsWith("en")) || voices[0];
  await new Promise(resolve => {
    const finish = () => { if(speechFinish === finish) speechFinish=null; resolve(); };
    speechFinish = finish;
    const speech = new SpeechSynthesisUtterance(text);
    speech.voice = voice;
    speech.rate = Number(localStorage.getItem("youai-rate") || 0.9);
    speech.pitch = 1;
    speech.volume = 0.9;
    speech.lang = voice.lang;
    speech.onend = finish;
    speech.onerror = event => { if (ticket === generation && !["interrupted","canceled"].includes(event.error)) showError("Voice playback was interrupted or unavailable."); finish(); };
    setState("speaking"); speechSynthesis.speak(speech);
  });
}
async function send(text, extras = {}) {
  text = text.trim(); if (!text) { idle(); return; }
  const memoryRequest=text.match(/^remember(?: that)?[: ,]+(.+)/i);
  if(memoryRequest){await stopAll();$('memory-text').value=memoryRequest[1];if(!$('panel').open)$('panel').showModal();$('memory-text').focus();showError('Review the proposed memory, then click Approve and remember. Nothing has been saved yet.');return;}
  if(window.handleLaptopCommand && await handleLaptopCommand(text))return;
  await stopAll(); const ticket = generation; showError("");
  $("sources").replaceChildren();
  setState("thinking"); turnId = crypto.randomUUID(); requestAbort = new AbortController();
  let speechQueue = Promise.resolve(), pendingSpeech = "", fullText = "", complete = false, failed = false;
  const speakPart = part => {
    speechQueue = speechQueue.then(()=>ticket===generation && !failed ? say(part,ticket) : undefined);
  };
  const consume = event => {
    if (ticket !== generation) return;
    if (event.type==="error") throw new Error(event.message);
    if (event.type==="progress") $("state").textContent=event.text;
    if(event.type==="sources") renderSources(event.sources,$("sources"));
    if (event.type==="token") {
      fullText += event.text; pendingSpeech += event.text;
      $("latest").hidden=false; $("latest-text").textContent=fullText;
      $("replay").disabled=true;
      while(pendingSpeech.length) {
        const sentence=pendingSpeech.match(/^([\s\S]*?[.!?](?:\s+|$))/);
        let length=sentence && sentence[1].length>=24 ? sentence[1].length : 0;
        if(!length && pendingSpeech.length>200) length=pendingSpeech.lastIndexOf(" ",180);
        if(length<=0) break;
        speakPart(pendingSpeech.slice(0,length).trim()); pendingSpeech=pendingSpeech.slice(length);
      }
    }
    if(event.type==="done") {
      complete=true; lastAnswer=event.text;
      $("latest-text").textContent=lastAnswer;
      if(pendingSpeech.trim()) speakPart(pendingSpeech.trim());
      pendingSpeech="";
    }
  };
  try {
    const response=await fetch("/api/chat/stream", {...json({text,turn_id:turnId,use_documents:$("use-documents").checked,document_ids:[...(window.selectedDocuments || [])],use_web:$("use-web").checked,...extras}),
      headers:{"Content-Type":"application/json","X-YouAI":"1"},signal:requestAbort.signal});
    if(!response.ok) { const data=await response.json(); throw new Error(data.detail || "The local answer could not start."); }
    const reader=response.body.getReader(), decoder=new TextDecoder();
    let pending="";
    while(true) {
      const {value,done}=await reader.read();
      pending+=decoder.decode(value,{stream:!done});
      let index;
      while((index=pending.indexOf("\n"))>=0) {
        const line=pending.slice(0,index); pending=pending.slice(index+1);
        if(line.trim()) consume(JSON.parse(line));
      }
      if(done) break;
    }
    if(pending.trim()) consume(JSON.parse(pending));
    if(ticket!==generation) return;
    if(!complete) throw new Error("The reply was interrupted before it finished. Please try again.");
    turnId=null;
    refreshHistory().catch(()=>{}); refreshReminders().catch(()=>{});
    await speechQueue;
  } catch (error) {
    failed=true;
    if (ticket === generation && error.name !== "AbortError") {
      speechFinish?.(); speechSynthesis.cancel(); window.desktop?.stopSpeech?.(); showError(error.message);
    }
  } finally {
    if (ticket === generation) { interruptionCapture?.close(); interruptionCapture=null; turnId = null; requestAbort = null; $("replay").disabled=!complete; idle(); }
  }
}
async function record(wakeMode = false) {
  if (recording) return;
  const ticket = generation;
  const fail = error => {
    if(ticket!==generation) return;
    releaseRecorder(); $("wake").checked=false; idle();
    showError(error.name==="NotAllowedError" ? "Allow microphone access to talk. You can still type below." : error.message || "Could not open your microphone.");
  };
  try {
    showError(""); setState("starting");
    const capture = new YouAudio({
      onWake:()=>{if(ticket===generation) setState("listening");},
      onError:fail,
      onAudio:async(audio,fromWake)=>{
        if(ticket!==generation) return;
        recording=null;
        if(!audio) {showError("I didn’t hear anything. Please try again.");idle();return;}
        setState("transcribing"); requestAbort=new AbortController();
        const form=new FormData(); form.append("audio",audio,"voice.wav");form.append("language",localStorage.getItem("youai-language")||"auto");
        try {
          const result=await api("/api/transcribe",{method:"POST",body:form,signal:requestAbort.signal});
          if(ticket!==generation) return;
          const text=fromWake ? result.text.replace(/^(?:hey|hey,)[\s,]+you\b[\s,.!?]*/i,"").trim() : result.text.trim();
          if(text) await send(text);
          else {showError("I heard the wake phrase, but no request. Tap the circle and try again.");idle();}
        } catch(error) {if(ticket===generation && error.name!=="AbortError") fail(error);}
      }
    });
    recording=capture;
    await capture.start(wakeMode);
    if(ticket===generation && !capture.closed) setState(wakeMode ? "armed" : "listening");
  } catch(error) {fail(error);}
}
$("orb").onclick = async () => {
  if (state === "listening" && recording) { recording.finish(); return; }
  if (state === "idle" || state === "armed") { await stopAll(); await record(); }
  else { await stopAll(); idle(); }
};
$("composer").onsubmit = async e => { e.preventDefault(); const value = $("prompt").value; if (value.trim()) { $("prompt").value=""; await send(value); } };
$("wake").onchange = async () => { await stopAll(); idle(); };
$("open-panel").onclick = async () => { $("panel").showModal(); await Promise.all([refreshHistory(),refreshDocuments(),window.refreshFeatures?.()]).catch(e=>showError(e.message)); };
$("close-panel").onclick = () => $("panel").close();
$("clear").onclick = async () => {
  if (!confirm("Delete the conversation saved on this laptop? Your notes will remain.")) return;
  await stopAll();
  try { await api("/api/history",{method:"DELETE"}); await refreshHistory(); $("latest").hidden=true; lastAnswer=""; }
  catch (e) { showError(e.message); }
  idle();
};
$("speak").onchange = () => { localStorage.setItem("youai-speak",String($("speak").checked)); if (!$("speak").checked) {speechFinish?.();speechSynthesis.cancel();window.desktop?.stopSpeech?.();} };
$("speak").checked = localStorage.getItem("youai-speak") !== "false";
$("replay").onclick = async () => { await stopAll(); const ticket=generation; await say(lastAnswer,ticket); if(ticket===generation) idle(); };
$("retry").onclick = refresh;
document.addEventListener("visibilitychange",async()=>{
  if(document.hidden){if(!(window.desktop && $("background-wake")?.checked))await stopAll();return;}
  if(state==="idle")idle();refreshReminders().catch(()=>{});
});
window.addEventListener("pagehide",()=>{ releaseRecorder(); interruptionCapture?.close(); speechSynthesis.cancel(); window.desktop?.stopSpeech?.(); });
speechSynthesis.getVoices();
const announced=new Set();
let remindersBusy=false;
async function refreshReminders() {
  if(remindersBusy) return;
  remindersBusy=true;
  try {
    const result=await api("/api/reminders");
    $("reminders").replaceChildren(); $("due-reminders").replaceChildren();
    let dueCount=0;
    for(const item of result.reminders) {
      const due=item.due_at<=result.now;
      const row=document.createElement("div"); row.className="note";
      const label=document.createElement("span");
      label.textContent=item.content+" · "+new Date(item.due_at*1000).toLocaleString(undefined,{timeZone:result.timezone});
      row.append(label);
      const done=document.createElement("button"); done.className="quiet"; done.textContent="Done";
      done.onclick=async()=>{await api("/api/reminders/"+item.id+"/done",{method:"POST"});await refreshReminders();};
      row.append(done);
      if(due) {
        dueCount++; $("due-reminders").append(row);
        if(!announced.has(item.id)) {
          announced.add(item.id);
          if("Notification" in window && Notification.permission==="granted") {
            const notification=new Notification("YouAI reminder",{body:item.content,tag:"youai-reminder-"+item.id});
            notification.onclick=()=>{window.focus();notification.close();};
          }
        }
      } else $("reminders").append(row);
    }
    $("reminder-alert").hidden=dueCount===0;
    $("reminder-summary").textContent=dueCount ? "Your reminders are ready" : "";
  } finally {remindersBusy=false;}
}
$("notifications").onclick=async()=>{
  if(!("Notification" in window)) {showError("Desktop notifications are unavailable in this browser.");return;}
  const permission=await Notification.requestPermission();
  $("notifications").textContent=permission==="granted" ? "Desktop notifications enabled" : "Notifications not enabled";
};
setState("idle"); refresh(); refreshHistory().catch(()=>{}); refreshReminders().catch(()=>{});
setInterval(()=>refreshReminders().catch(()=>{}),3000);

function renderSources(sources, container) {
  for(const source of sources) {
    const details=document.createElement("details"), summary=document.createElement("summary"), excerpt=document.createElement("p");
    summary.textContent="["+source.label+"] "+source.name+(source.kind==="web" ? " · web search snippet" : " · page "+source.page);
    if(source.url?.startsWith("https://")){const link=document.createElement("a");link.href=source.url;link.textContent="Open source";link.target="_blank";link.rel="noopener noreferrer";details.append(link);}
    excerpt.textContent=source.excerpt; details.append(summary,excerpt); container.append(details);
  }
}
async function refreshDocuments() {
  const result=await api("/api/documents?q="+encodeURIComponent($("document-search")?.value||""));
  $("documents").replaceChildren();
  for(const doc of result.documents) {
    const row=document.createElement("div"); row.className="note";
    const label=document.createElement("span"); label.textContent=doc.name+" · "+doc.chunks+" passages";
    const remove=document.createElement("button"); remove.className="quiet"; remove.textContent="Remove";
    remove.onclick=async()=>{
      if(!confirm("Remove "+doc.name+" from future document searches? Past conversation answers and excerpts remain until you clear history."))return;
      await api("/api/documents/"+doc.id,{method:"DELETE"});await refreshDocuments();
    };
    const select=document.createElement("input");select.type="checkbox";select.setAttribute("aria-label","Use "+doc.name);select.checked=window.selectedDocuments?.has(doc.id)||false;
    select.onchange=()=>{window.selectedDocuments ||= new Set();select.checked?window.selectedDocuments.add(doc.id):window.selectedDocuments.delete(doc.id);};
    const summarize=document.createElement("button");summarize.className="quiet";summarize.textContent="Summarize";summarize.onclick=()=>{$("panel").close();send("Summarize "+doc.name,{summary_document:doc.id,use_web:false});};
    row.append(select,label,summarize,remove);
    for(const warning of doc.warnings) {const p=document.createElement("p");p.className="panel-note";p.textContent=warning;row.append(p);}
    $("documents").append(row);
  }
}
$("document-upload").onsubmit=async event=>{
  event.preventDefault(); const file=$("document-file").files[0];
  if(!file){$("document-status").textContent="Choose a document first.";return;}
  $("import-document").disabled=true;$("document-status").textContent="Reading and indexing your document locally…";
  try {
    const form=new FormData();form.append("document",file);form.append("ocr_languages",$("ocr-language").value);
    const result=await api("/api/documents",{method:"POST",body:form});
    $("document-status").textContent=result.duplicate ? "This document is already indexed." : "Ready to search. "+result.warnings.join(" ");
    await refreshDocuments();$("use-documents").checked=true;
  } catch(error){$("document-status").textContent=error.message;}
  finally{$("import-document").disabled=false;}
};
$("pair-phone").onclick=async()=>{
  const container=$("pairing-result");container.replaceChildren();
  try {
    const result=await api("/api/mobile/pairing");
    const image=document.createElement("img");image.src=result.qr;image.alt="Private Android pairing QR";image.width=250;
    const text=document.createElement("p");text.className="panel-note";text.textContent=result.url;
    const input=document.createElement("textarea");input.value=result.link;input.readOnly=true;input.setAttribute("aria-label","Private pairing link to copy into Android app");
    container.append(image,text,input);
  }catch(error){container.textContent=error.message;}
};
if(window.YouAIPlatform?.native) {$("phone-pairing").hidden=true;document.querySelector("footer>span:last-child").textContent="YOU / ANDROID · LAPTOP CONNECTED";}

async function startInterruption() {
  let interrupted=false, currentTicket=generation;
  const capture=new YouAudio({
    onWake:async()=>{
      interrupted=true; interruptionCapture=null;
      await stopAll();currentTicket=generation;recording=capture;setState("listening");
    },
    onError:error=>{interruptionCapture=null;if(interrupted){recording=null;idle();}showError(error.message);},
    onAudio:async(audio)=>{
      if(!interrupted||currentTicket!==generation)return;
      recording=null;setState("transcribing");
      try {
        if(!audio){idle();return;}
        const form=new FormData();form.append("audio",audio,"interruption.wav");form.append("language",localStorage.getItem("youai-language")||"auto");
        const result=await api("/api/transcribe",{method:"POST",body:form});
        if(currentTicket!==generation)return;
        const text=result.text.replace(/^(?:hey|hey,)[\s,]+you\b[\s,.!?]*/i,"").trim();
        if(text)await send(text);else idle();
      }catch(error){if(currentTicket===generation){showError(error.message);idle();}}
    }
  });
  interruptionCapture=capture;
  try{await capture.start(true);}catch(error){interruptionCapture=null;showError("Spoken interruption unavailable: "+error.message);}
}
