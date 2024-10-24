import fs from 'fs';
import decodeAudio from 'audio-decode';
import WebSocket from 'ws';

// Converts Float32Array of audio data to PCM16 ArrayBuffer
function floatTo16BitPCM(float32Array) {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return buffer;
}

// Converts a Float32Array to base64-encoded PCM16 data
function base64EncodeAudio(float32Array) {
    const arrayBuffer = floatTo16BitPCM(float32Array);
    let binary = '';
    let bytes = new Uint8Array(arrayBuffer);
    const chunkSize = 0x8000; // 32KB chunk size
    for (let i = 0; i < bytes.length; i += chunkSize) {
        let chunk = bytes.subarray(i, i + chunkSize);
        binary += String.fromCharCode.apply(null, chunk);
    }
    return Buffer.from(binary, 'binary').toString('base64');
}

// Load and process the audio file (assumes mono .wav file)
async function processAudio(filePath) {
    try {
        const myAudio = fs.readFileSync(filePath);
        const audioBuffer = await decodeAudio(myAudio);
        const channelData = audioBuffer.getChannelData(0); // using the first channel
        return base64EncodeAudio(channelData);
    } catch (error) {
        console.error('Error processing audio:', error);
        return null;
    }
}

// Establish WebSocket connection with OpenAI API
async function connectToOpenAI() {
    const url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01";
    const ws = new WebSocket(url, {
        headers: {
            "Authorization": "Bearer " + process.env.OPENAI_API_KEY,
            "OpenAI-Beta": "realtime=v1",
        },
    });

    ws.on('open', async function open() {
        console.log("Connected to server.");

        // Process the audio file
        const base64AudioData = await processAudio('./output.wav');
        
        if (base64AudioData) {
            // Create and send the audio input event
            const audioEvent = {
                type: 'conversation.item.create',
                item: {
                    type: 'message',
                    role: 'user',
                    content: [
                        {
                            type: 'input_audio',
                            audio: base64AudioData
                        }
                    ]
                }
            };
            ws.send(JSON.stringify(audioEvent));
        } else {
            console.error('Failed to process audio file.');
        }

        // Create and send the text-based response request
        const textEvent = {
            type: 'response.create',
            response: {
                modalities: ["text", "audio"],
                instructions: "Please assist the user.",
            }
        };
        ws.send(JSON.stringify(textEvent));
    });

    ws.on('message', function incoming(message) {
        console.log('Received:', JSON.parse(message.toString()));
    });

    ws.on('error', function error(err) {
        console.error('WebSocket error:', err);
    });

    ws.on('close', function close() {
        console.log('Disconnected from server.');
    });
}

// Start the connection
connectToOpenAI();