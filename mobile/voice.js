/* Microphone on the composer. Speech becomes the ask; chips stay in place. */
(function () {
    const MAX_MS = 12000;

    function encodeWav(samples, sampleRate) {
        const buffer = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buffer);
        const write = (offset, text) => {
            for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
        };
        write(0, "RIFF");
        view.setUint32(4, 36 + samples.length * 2, true);
        write(8, "WAVE");
        write(12, "fmt ");
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        write(36, "data");
        view.setUint32(40, samples.length * 2, true);
        let offset = 44;
        for (let i = 0; i < samples.length; i += 1, offset += 2) {
            const sample = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
        }
        return new Blob([buffer], { type: "audio/wav" });
    }

    function downsample(buffer, fromRate, toRate) {
        if (fromRate === toRate) return buffer;
        const ratio = fromRate / toRate;
        const length = Math.round(buffer.length / ratio);
        const result = new Float32Array(length);
        for (let i = 0; i < length; i += 1) {
            const start = Math.floor(i * ratio);
            const end = Math.min(buffer.length, Math.floor((i + 1) * ratio));
            let sum = 0;
            let count = 0;
            for (let j = start; j < end; j += 1) {
                sum += buffer[j];
                count += 1;
            }
            result[i] = count ? sum / count : 0;
        }
        return result;
    }

    window.mountVoice = function mountVoice(options) {
        const button = options.button;
        const input = options.input;
        const status = options.status;
        const ask = options.ask;
        if (!button || !input) return;

        let recording = null;
        let busy = false;

        function setStatus(text) {
            if (!status) return;
            status.textContent = text || "";
        }

        function setListening(on) {
            button.classList.toggle("listening", on);
            button.setAttribute("aria-pressed", on ? "true" : "false");
            button.setAttribute("aria-label", on ? "Stop and search" : "Speak your request");
        }

        async function stopRecording() {
            const current = recording;
            recording = null;
            setListening(false);
            if (!current) return null;
            clearTimeout(current.timer);
            current.processor.disconnect();
            current.source.disconnect();
            current.stream.getTracks().forEach((track) => track.stop());
            const rate = current.context.sampleRate;
            await current.context.close();
            const length = current.chunks.reduce((sum, chunk) => sum + chunk.length, 0);
            if (!length || Date.now() - current.started < 350) return null;
            const merged = new Float32Array(length);
            let offset = 0;
            current.chunks.forEach((chunk) => {
                merged.set(chunk, offset);
                offset += chunk.length;
            });
            return encodeWav(downsample(merged, rate, 16000), 16000);
        }

        async function startRecording() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                setStatus("This browser can't use the microphone. Type instead.");
                return;
            }
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
            });
            const context = new AudioContext();
            if (context.state === "suspended") await context.resume();
            const source = context.createMediaStreamSource(stream);
            const processor = context.createScriptProcessor(4096, 1, 1);
            const gain = context.createGain();
            gain.gain.value = 0;
            const chunks = [];
            processor.onaudioprocess = (event) => {
                if (!recording) return;
                chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
            };
            source.connect(processor);
            processor.connect(gain);
            gain.connect(context.destination);
            recording = { stream, context, source, processor, chunks, started: Date.now() };
            setListening(true);
            setStatus("");
            input.placeholder = "Listening…";
            recording.timer = setTimeout(() => { finish(); }, MAX_MS);
        }

        async function finish() {
            if (busy) return;
            busy = true;
            button.disabled = true;
            if (ask) ask.disabled = true;
            const clip = await stopRecording();
            input.placeholder = "Something quiet…";
            if (!clip) {
                setStatus("Hold on a moment and say what you'd like.");
                busy = false;
                button.disabled = false;
                if (ask) ask.disabled = false;
                return;
            }
            setStatus("Hearing you…");
            try {
                const response = await fetch("/api/transcribe", {
                    method: "POST",
                    headers: { "Content-Type": "audio/wav" },
                    body: clip,
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.detail || "I couldn't hear that.");
                const text = (data.text || "").trim();
                if (!text) {
                    setStatus("I didn't catch that. Try again.");
                    if (ask) ask.disabled = false;
                    return;
                }
                setStatus("");
                input.value = text;
                options.onUtterance(text, data.language || "");
            } catch (error) {
                setStatus(error.message || "I couldn't hear that. Try again.");
                if (ask) ask.disabled = false;
            } finally {
                busy = false;
                button.disabled = false;
            }
        }

        button.addEventListener("click", () => {
            if (busy) return;
            if (recording) {
                finish();
                return;
            }
            startRecording().catch(() => {
                setListening(false);
                setStatus("Allow the microphone, or type instead.");
            });
        });
    };
})();
