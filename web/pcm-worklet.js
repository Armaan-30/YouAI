class PCMRecorder extends AudioWorkletProcessor {
  constructor() { super(); this.buffer = new Int16Array(1280); this.used = 0; }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) for (const sample of channel) {
      this.buffer[this.used++] = Math.max(-32768, Math.min(32767, Math.round(sample * 32767)));
      if (this.used === this.buffer.length) {
        this.port.postMessage(this.buffer.buffer, [this.buffer.buffer]);
        this.buffer = new Int16Array(1280); this.used = 0;
      }
    }
    return true;
  }
}
registerProcessor("pcm-recorder", PCMRecorder);
