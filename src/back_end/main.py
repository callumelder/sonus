from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections
active_connections: list[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("New WebSocket connection attempt...")
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")
        
        while True:
            data = await websocket.receive_text()
            try:
                json_data = json.loads(data)
                if json_data.get('type') == 'audio_metering':
                    logger.info(f"Received audio metering: {json_data.get('value')}")
                elif json_data.get('type') == 'audio_data':
                    logger.info(f"Received audio data with metering: {json_data.get('metering')}")
                    # Here you would process the audio data
                
                # Echo back confirmation
                await websocket.send_text(json.dumps({
                    "status": "received",
                    "type": json_data.get('type')
                }))
                
            except json.JSONDecodeError:
                logger.error("Received invalid JSON data")
                
    except Exception as e:
        logger.error(f"WebSocket error occurred: {str(e)}")
    finally:
        logger.info("WebSocket connection closed")

@app.get("/")
async def root():
    logger.info("Health check endpoint called")
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")