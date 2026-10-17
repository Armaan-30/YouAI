/* Android only supplies playback and pairing; inference stays on the laptop. */
(() => {
  if (!window.NativeYou) return;
  const pending = new Map(); let sequence = 0;
  const cancel = () => { NativeYou.stop(); for (const finish of pending.values()) finish(); pending.clear(); };
  window.onYouSpeech = id => { pending.get(id)?.(); pending.delete(id); };
  window.YouAIPlatform = {native:true, token:()=>NativeYou.getToken(), speak:text=>new Promise(resolve=>{
    const id=String(++sequence); pending.set(id,resolve); NativeYou.speak(text,id);
  })};
  const original=window.fetch.bind(window);
  window.fetch=(input,options={})=>{
    const url=new URL(typeof input==='string'?input:input.url,location.href);
    if(url.origin===location.origin && url.pathname.startsWith('/api/')) {
      const headers=new Headers(options.headers || (input instanceof Request?input.headers:undefined));
      headers.set('Authorization','Bearer '+NativeYou.getToken()); options={...options,headers};
    }
    return original(input,options);
  };
  Object.defineProperty(window,'speechSynthesis',{value:{cancel,getVoices:()=>[],addEventListener:()=>{},removeEventListener:()=>{}}});
})();
