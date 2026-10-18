// Hosted wake listening uses browser recognition, never the laptop WebSocket.
class YouBrowserWake {
  static supported() { return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition); }
  constructor({onReady,onWake,onText,onError}) {
    Object.assign(this,{onReady,onWake,onText,onError});
    this.closed=false;this.awake=false;this.quickEnds=0;
  }
  start() {
    if(this.closed)return;
    const Recognition=window.SpeechRecognition || window.webkitSpeechRecognition;
    if(!Recognition){this.fail('Hey You is unavailable in this browser. Use the microphone button instead.');return;}
    const recognition=this.recognition=new Recognition();
    recognition.lang=localStorage.getItem('youai-language')==='auto' || !localStorage.getItem('youai-language') ? (navigator.language || 'en-US') : localStorage.getItem('youai-language');
    recognition.continuous=true;recognition.interimResults=false;
    this.startTimer=setTimeout(()=>this.fail('Browser wake listening did not start. Check microphone permission or use the circle.'),12000);
    recognition.onstart=()=>{clearTimeout(this.startTimer);if(!this.closed){this.started=Date.now();if(!this.awake)this.onReady();}};
    recognition.onresult=event=>{
      if(this.closed)return;
      for(let i=event.resultIndex;i<event.results.length;i++){
        if(!event.results[i].isFinal)continue;
        let text=event.results[i][0].transcript.trim();
        if(!this.awake){
          const match=text.match(/^hey[\s,]+you\b[\s,.!?]*/i);
          if(!match)continue;
          this.awake=true;this.onWake();text=text.slice(match[0].length).trim();
          this.commandTimer=setTimeout(()=>this.fail('I heard Hey You, but no request. Toggle Hey You to retry, or tap the circle.'),12000);
        }
        if(text){this.close();this.onText(text);return;}
      }
    };
    recognition.onerror=event=>{
      if(this.closed || event.error==='no-speech')return;
      const message=['not-allowed','service-not-allowed','audio-capture'].includes(event.error)
        ? 'Allow microphone and speech recognition access, then enable Hey You again. You can also type.'
        : 'Browser speech recognition is unavailable. Check your connection, toggle Hey You to retry, or use the microphone button.';
      this.fail(message);
    };
    recognition.onend=()=>{
      clearTimeout(this.startTimer);
      if(this.closed)return;
      this.quickEnds=Date.now()-(this.started || Date.now())<2000 ? this.quickEnds+1 : 0;
      if(this.quickEnds>=3){this.fail('This browser keeps stopping wake listening. Use the microphone button instead.');return;}
      this.restartTimer=setTimeout(()=>this.start(),300);
    };
    try{recognition.start();}catch{this.fail('Could not start browser wake listening. Toggle Hey You to retry or use the microphone button.');}
  }
  finish() { this.fail('No complete request heard yet. Tap the circle to record a request.'); }
  fail(message) { if(this.closed)return;this.close();this.onError(new Error(message)); }
  close() {
    this.closed=true;clearTimeout(this.restartTimer);clearTimeout(this.commandTimer);clearTimeout(this.startTimer);
    if(this.recognition){this.recognition.onend=null;this.recognition.onresult=null;this.recognition.onerror=null;this.recognition.onstart=null;try{this.recognition.abort();}catch{}}
  }
}
