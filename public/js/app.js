import { RTCManager } from './webrtc.js';

const rtc = new RTCManager();

// DOM Elements
const modeInitiator = document.getElementById('mode-initiator');
const modeReceiver = document.getElementById('mode-receiver');
const initiatorFlow = document.getElementById('initiator-flow');
const receiverFlow = document.getElementById('receiver-flow');

const startBtn = document.getElementById('start-btn');
const offerDisplay = document.getElementById('offer-display');
const offerArea = document.getElementById('offer-area');
const copyOfferBtn = document.getElementById('copy-offer-btn');
const finalizeFlow = document.getElementById('finalize-flow');
const answerInput = document.getElementById('answer-input');
const connectBtn = document.getElementById('connect-btn');

const offerInput = document.getElementById('offer-input');
const joinBtn = document.getElementById('join-btn');
const answerDisplay = document.getElementById('answer-display');
const answerArea = document.getElementById('answer-area');
const copyAnswerBtn = document.getElementById('copy-answer-btn');

const handshakeUI = document.getElementById('handshake-ui');
const chatUI = document.getElementById('chat-ui');
const messages = document.getElementById('messages');
const msgInput = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');
const status = document.getElementById('status');

// Mode Selection
modeInitiator.addEventListener('click', () => {
    initiatorFlow.style.display = 'block';
    receiverFlow.style.display = 'none';
});

modeReceiver.addEventListener('click', () => {
    receiverFlow.style.display = 'block';
    initiatorFlow.style.display = 'none';
});

// Initiator: Generate Offer
startBtn.addEventListener('click', async () => {
    status.innerText = 'Status: Generating Offer...';
    try {
        const offer = await rtc.createOffer();
        offerArea.value = offer;
        offerDisplay.style.display = 'block';
        finalizeFlow.style.display = 'block';
        startBtn.style.display = 'none';
        status.innerText = 'Status: Waiting for Peer Answer';
    } catch (e) {
        console.error(e);
        status.innerText = 'Status: Error generating offer';
    }
});

copyOfferBtn.addEventListener('click', () => {
    offerArea.select();
    document.execCommand('copy');
});

// Initiator: Connect
connectBtn.addEventListener('click', async () => {
    const answer = answerInput.value.trim();
    if (!answer) return alert('Please paste the answer');

    status.innerText = 'Status: Connecting...';
    try {
        await rtc.finalize(answer);
    } catch (e) {
        console.error(e);
        status.innerText = 'Status: Error connecting';
    }
});

// Receiver: Generate Answer
joinBtn.addEventListener('click', async () => {
    const offer = offerInput.value.trim();
    if (!offer) return alert('Please paste the offer');

    status.innerText = 'Status: Generating Answer...';
    try {
        const answer = await rtc.createAnswer(offer);
        answerArea.value = answer;
        answerDisplay.style.display = 'block';
        joinBtn.style.display = 'none';
        status.innerText = 'Status: Waiting for Peer Connection';
    } catch (e) {
        console.error(e);
        status.innerText = 'Status: Error generating answer';
    }
});

copyAnswerBtn.addEventListener('click', () => {
    answerArea.select();
    document.execCommand('copy');
});

// Chat Logic
rtc.onConnected = () => {
    status.innerText = 'Status: Connected';
    handshakeUI.style.display = 'none';
    chatUI.style.display = 'block';
};

rtc.onMessage = (msg) => {
    const div = document.createElement('div');
    div.innerText = 'Peer: ' + msg;
    messages.appendChild(div);
};

sendBtn.addEventListener('click', () => {
    const msg = msgInput.value;
    if (msg) {
        rtc.sendMessage(msg);
        const div = document.createElement('div');
        div.innerText = 'You: ' + msg;
        messages.appendChild(div);
        msgInput.value = '';
    }
});
