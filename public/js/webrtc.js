export class RTCManager {
    constructor() {
        this.pc = null;
        this.dc = null;
        this.onConnected = null;
        this.onMessage = null;
    }

    reset() {
        if (this.pc) this.pc.close();
        // Use default configuration (no STUN/TURN) for local P2P
        this.pc = new RTCPeerConnection();

        this.pc.onconnectionstatechange = () => {
            console.log('Connection state:', this.pc.connectionState);
            if (this.pc.connectionState === 'connected') {
                if (this.onConnected) this.onConnected();
            }
        };
    }

    async createOffer() {
        this.reset();
        this.dc = this.pc.createDataChannel('chat');
        this.setupDataChannel(this.dc);

        const offer = await this.pc.createOffer();
        await this.pc.setLocalDescription(offer);

        await this.waitForIceGathering();
        return this.encode(this.pc.localDescription);
    }

    async createAnswer(offerStr) {
        this.reset();
        this.pc.ondatachannel = (event) => {
            this.dc = event.channel;
            this.setupDataChannel(this.dc);
        };

        const offer = this.decode(offerStr);
        await this.pc.setRemoteDescription(offer);

        const answer = await this.pc.createAnswer();
        await this.pc.setLocalDescription(answer);

        await this.waitForIceGathering();
        return this.encode(this.pc.localDescription);
    }

    async finalize(answerStr) {
        const answer = this.decode(answerStr);
        await this.pc.setRemoteDescription(answer);
    }

    setupDataChannel(dc) {
        dc.onopen = () => {
            console.log('DataChannel open');
            // We can also trigger onConnected here if we prefer waiting for DC
            if (this.onConnected) this.onConnected();
        };
        dc.onmessage = (e) => {
            if (this.onMessage) this.onMessage(e.data);
        };
    }

    waitForIceGathering() {
        return new Promise((resolve) => {
            if (this.pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                const check = () => {
                    if (this.pc.iceGatheringState === 'complete') {
                        this.pc.removeEventListener('icegatheringstatechange', check);
                        resolve();
                    }
                };
                this.pc.addEventListener('icegatheringstatechange', check);
            }
        });
    }

    encode(obj) {
        return btoa(JSON.stringify(obj));
    }

    decode(str) {
        return JSON.parse(atob(str));
    }

    sendMessage(msg) {
        if (this.dc && this.dc.readyState === 'open') {
            this.dc.send(msg);
        }
    }
}
