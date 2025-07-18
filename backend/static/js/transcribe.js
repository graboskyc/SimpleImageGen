function init() {
    return {
        listening: false,
        status: '',
        ws: null,
        transcript: [''],
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
                const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
                this.ws = new WebSocket(wsProtocol + "://" + window.location.host + "/api/transcribe");
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
                    //console.log('Received message:', event.data);
                    var payload = JSON.parse(event.data);
                    if(this.transcript.length - 1 < payload["id"]) {
                        this.transcript.push(payload["text"]);
                    } else {
                        this.transcript[payload["id"]] = payload["text"];
                    }
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
        },
        copyTranscript() {
            if (this.transcript) {
                navigator.clipboard.writeText(this.transcript.join('\n')).then(() => {
                    this.status = 'Transcript copied to clipboard!';
                }, () => {
                    this.status = 'Failed to copy transcript.';
                });
            }
        },
        summary: '',
        summarizeTranscript: async function() {
            this.status = 'Summarizing transcript...';
            const formData = new FormData();
            formData.append('transcript', this.transcript.join('\n'));
            try {
                const response = await fetch('/api/summarize', {
                    method: 'POST',
                    body: formData
                });
                if (response.ok) {
                    const data = await response.json();
                    console.log('Summary response:', data);
                    // Fireworks returns either a summary or a full result
                    if (data.summary) {
                        this.summary = data.summary;
                    } else if (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) {
                        this.summary = data.choices[0].message.content;
                    } else {
                        this.summary = 'No summary returned.';
                    }
                    this.status = 'Summary complete.';
                } else {
                    this.status = 'Error summarizing transcript.';
                    this.summary = '';
                }
            } catch (err) {
                this.status = 'Error summarizing transcript.';
                this.summary = '';
            }
        }
    }
}