# Sonus - Voice Controlled AI Email Assistant

Sonus is an intelligent voice assistant that helps you manage your emails through natural spoken conversation. Using advanced speech recognition and AI technologies, Sonus enables hands-free email management with a human-like conversational interface.

## Features

- Natural Voice Interactions: Converse naturally with the assistant to manage your email
- Email Management: Create, send, search, and read emails using just your voice
- Real-time Speech Processing: Continuous speech recognition with interim and final transcripts
- Responsive Voice Feedback: Immediate voice responses using Text-to-Speech technology
- Mobile & Desktop Compatible: React Native mobile app with backend server communication

## Architecture

Sonus uses a multi-tier architecture:

1. Mobile Application: React Native frontend with Expo Audio for voice capture
2. Flask Server: WebSocket-based communication layer for real-time audio streaming
3. Python Backend: LangGraph workflow orchestration of different AI components
4. Cloud Services:
   - Claude AI API for natural language understanding
   - Google Speech-to-Text for voice recognition
   - ElevenLabs for high-quality text-to-speech synthesis
   - Gmail API for email management

## Technical Stack

### Frontend
- React Native with Expo
- WebSocket for real-time communication
- Animated UI components for visual feedback

### Backend
- Python Flask for WebSocket server
- LangGraph for workflow orchestration
- Google Cloud Speech API for voice recognition
- ElevenLabs API for text-to-speech
- Langchain for AI assistant capabilities
- Google Gmail API for email operations
