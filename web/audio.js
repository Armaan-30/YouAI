// One continuous 16 kHz audio stream, shared between activation and command capture.
class YouAudio {
  constructor({onWake, onAudio, onError}) {
    Object.assign(this, {onWake, onAudio, onError});
    this.closed = false; this.mode = "starting"; this.frames = []; this.ring = [];
    this.noise = 0.003; this.heard = false;
  }
  async start(wakeMode) {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if (this.closed) { this.stream.getTracks().forEach(t=>t.stop()); return; }
      this.context = new AudioContext({sampleRate:16000});
      await this.context.resume();
      await this.context.audioWorklet.addModule("/static/pcm-worklet.js");
      if (this.closed) { this.close(); return; }
      if (this.context.sampleRate !== 16000) throw new Error("Your browser does not support the required microphone sample rate.");
      this.node = new AudioWorkletNode(this.context, "pcm-recorder");
      this.source = this.context.createMediaStreamSource(this.stream);
      this.source.connect(this.node);
      this.mute = this.context.createGain(); this.mute.gain.value = 0;
      this.node.connect(this.mute).connect(this.context.destination);
      this.node.port.onmessage = e => this.frame(new Int16Array(e.data));
      if (wakeMode) await this.arm();
      else this.listen(false);
    } catch (error) { this.close(); throw error; }
  }
  arm() {
    return new Promise((resolve,reject) => {
      const ws = this.socket = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/api/wake?stability=" + (localStorage.getItem("youai-stability")||"2"), window.YouAIPlatform?.native ? ["youai", window.YouAIPlatform.token()] : []);
      const timer = setTimeout(()=>{ reject(new Error("Wake recognition did not start. Use the button or retry.")); this.close(); },12000);
      ws.onmessage = e => {
        const result = JSON.parse(e.data);
        if (result.type === "ready") { clearTimeout(timer); this.mode="armed"; resolve(); }
        if (result.type === "wake" && this.mode === "armed") {
          this.listen(true); this.onWake(); ws.close();
        }
        if (result.type === "error") { clearTimeout(timer); const error=new Error(result.message); reject(error); this.fail(error); }
      };
      ws.onerror = () => { clearTimeout(timer); const error=new Error("Wake recognition disconnected. Use the button or retry."); reject(error); this.fail(error); };
      ws.onclose = () => {
        clearTimeout(timer);
        if (this.mode === "starting") reject(new Error("Wake recognition could not connect."));
        else if (!this.closed && this.mode === "armed") this.fail(new Error("Wake recognition disconnected. Toggle Hey You to reconnect."));
      };
    });
  }
  listen(fromWake) {
    this.mode="listening"; this.frames=fromWake ? this.ring.slice() : [];
    this.started=performance.now(); this.lastSound=this.started; this.heard=false;
    this.fromWake=fromWake;
    this.limit=setTimeout(()=>this.finish(),60000);
  }
  frame(pcm) {
    if(this.closed) return;
    this.ring.push(pcm); if(this.ring.length>20) this.ring.shift(); // 1.6 seconds of pre-roll
    if(this.mode==="armed") {
      if(this.socket?.readyState===WebSocket.OPEN) {
        if(this.socket.bufferedAmount>32000) { this.fail(new Error("Wake recognition is falling behind. Please reconnect.")); return; }
        this.socket.send(pcm.buffer);
      }
      return;
    }
    if(this.mode!=="listening") return;
    this.frames.push(pcm);
    const rms=Math.sqrt(pcm.reduce((sum,n)=>sum+(n/32768)**2,0)/pcm.length);
    const now=performance.now(), threshold=Math.max(0.007, Math.min(0.025,this.noise*3));
    if(rms>threshold) { this.heard=true; this.lastSound=now; }
    else this.noise=this.noise*0.97+rms*0.03;
    if(this.heard && now-this.lastSound>Number(localStorage.getItem("youai-pause")||1100) && now-this.started>700) this.finish();
    // A bare wake phrase should leave ample time to begin the actual request.
    else if(!this.heard && now-this.started>10000) this.finish();
  }
  finish() {
    if(this.closed || this.mode!=="listening") return;
    const frames=this.frames, heard=this.heard || (this.fromWake && frames.length>0), fromWake=this.fromWake;
    this.close();
    this.onAudio(heard ? YouAudio.wav(frames) : null, fromWake);
  }
  fail(error) { if(this.closed) return; this.close(); this.onError(error); }
  close() {
    this.closed=true; clearTimeout(this.limit);
    this.socket?.close();
    this.stream?.getTracks().forEach(t=>t.stop());
    this.source?.disconnect(); this.node?.disconnect(); this.mute?.disconnect();
    if(this.context && this.context.state!=="closed") this.context.close().catch(()=>{});
    this.ring=[]; this.frames=[];
  }
  static wav(frames) {
    const samples=frames.reduce((n,f)=>n+f.length,0);
    const data=new ArrayBuffer(44+samples*2), view=new DataView(data);
    const word=(offset,s)=>[...s].forEach((c,i)=>view.setUint8(offset+i,c.charCodeAt(0)));
    word(0,"RIFF"); view.setUint32(4,36+samples*2,true); word(8,"WAVE");
    word(12,"fmt "); view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
    view.setUint32(24,16000,true); view.setUint32(28,32000,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
    word(36,"data"); view.setUint32(40,samples*2,true);
    let offset=44; for(const frame of frames) for(const n of frame) {view.setInt16(offset,n,true);offset+=2;}
    return new Blob([data],{type:"audio/wav"});
  }
}
window.YouAudio = YouAudio;
