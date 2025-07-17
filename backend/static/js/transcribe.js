function init() {
    return {
        listening: false,
        status: '',
        ws: null,
        transcript: "",
        audioContext: null,
        processor: null,
        stream: null,
        startListening() {
            if (this.listening) {
                this.stopListening();
                return;
            }
            this.status = 'Requesting microphone...';
            navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
                this.status = 'Microphone active, connecting...';
                this.ws = new WebSocket('ws://' + window.location.host + '/api/transcribe');
                this.ws.binaryType = 'arraybuffer';
                this.ws.onopen = () => {
                    this.status = 'Streaming audio...';
                    this.listening = true;
                    this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                    this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
                    this.stream = this.audioContext.createMediaStreamSource(stream);
                    this.stream.connect(this.processor);
                    this.processor.connect(this.audioContext.destination);
                    this.processor.onaudioprocess = (e) => {
                        if (this.ws.readyState === WebSocket.OPEN) {
                            // Get PCM samples from the buffer
                            let input = e.inputBuffer.getChannelData(0);
                            let pcm = new Int16Array(input.length);
                            for (let i = 0; i < input.length; i++) {
                                let s = Math.max(-1, Math.min(1, input[i]));
                                pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                            }
                            this.ws.send(pcm.buffer);
                        }
                    };
                };
                this.ws.onmessage = (event) => {
                    console.log('Received message:', event.data);
                    this.transcript = event.data;
                };
                this.ws.onclose = () => {
                    this.status = 'WebSocket closed.';
                    this.listening = false;
                    if (this.processor) {
                        this.processor.disconnect();
                    }
                    if (this.audioContext) {
                        this.audioContext.close();
                    }
                };
                this.ws.onerror = (e) => {
                    this.status = 'WebSocket error.';
                    this.listening = false;
                };
            }).catch(err => {
                this.status = 'Microphone error: ' + err;
            });
        },
        stopListening() {
            if (this.ws) {
                this.ws.close();
            }
            this.listening = false;
            this.status = 'Stopped.';
            if (this.processor) {
                this.processor.disconnect();
            }
            if (this.audioContext) {
                this.audioContext.close();
            }
        }
    }
}