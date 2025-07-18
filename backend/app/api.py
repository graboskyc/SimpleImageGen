import asyncio
from fastapi import FastAPI, Response, File, UploadFile, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import datetime
from fastapi.staticfiles import StaticFiles
import json
import os
import requests
from typing import Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import base64
import json
import time
import threading
import websocket as wsclient
import urllib.parse

api_app = FastAPI(title="api-app")
app = FastAPI(title="spa-app")
app.mount("/api", api_app)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

FIREWORKSAPIKEY = os.environ["FIREWORKSKEY"].strip()

@api_app.get("/hello")
async def hello():
    return {"message": "Hello World"}


@api_app.post("/generate")
async def generate(
    file: UploadFile = File(None),
    prompt: str = Form("A beautiful sunset over the ocean"),
    safety: int = Form(2)  # Default safety level
):
    url = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-kontext-pro"

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FIREWORKSAPIKEY}",
        }

        data = {
            "prompt": prompt,
            "safety_tolerance": safety
        }

        # if a file is provided
        if file:
            headers["Accept"] = "image/jpeg"
            image_base64 = base64.b64encode(file.file.read()).decode('utf-8')
            data["input_image"] = f"data:image/jpeg;base64,{image_base64}"
            print("Using image")
        else:
            print("prompt only")
            headers["Accept"] = "application/json"

        response = requests.post(url, headers=headers, json=data)
        print(data)

        if response.status_code == 200:
            result = response.json()
            #print(f"Response from Fireworks API: {json.dumps(result, indent=2)}")
            if "request_id" in result:
                # Poll for completion
                result_endpoint = f"{url}/get_result"
                for attempt in range(60):
                    time.sleep(1)
                    print(f"Polling for result, attempt {attempt + 1}/60 for request_id: {result['request_id']}")
                    poll_response = requests.post(result_endpoint, 
                        headers=headers, 
                        json={"id": result["request_id"]})
                    if poll_response.status_code == 200:
                        poll_result = poll_response.json()
                        if poll_result.get("status") in ["Ready", "Complete", "Finished"]:
                            print(poll_result)
                            image_data = poll_result.get("result", {}).get("sample")
                            if image_data:
                                if isinstance(image_data, str) and image_data.startswith("http"):
                                    # If the result is a URL, fetch the image
                                    img_resp = requests.get(image_data)
                                    if img_resp.status_code == 200:
                                        return StreamingResponse(
                                            iter([img_resp.content]),
                                            media_type="image/jpeg"
                                        )
                                    else:
                                        raise HTTPException(status_code=502, detail="Failed to fetch image from URL.")
                                else:
                                    # Base64 image data
                                    img_bytes = base64.b64decode(image_data)
                                    return StreamingResponse(
                                        iter([img_bytes]),
                                        media_type="image/jpeg"
                                    )
                            break
                        elif poll_result.get("status") in ["Failed", "Error"]:
                            raise HTTPException(status_code=502, detail=poll_result.get("details", "Generation failed."))
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Something went wrong: {str(e)}')
    finally:
        if file:
            file.file.close()

    print("Image generation completed.")



@api_app.websocket("/transcribe")
async def transcribe_ws(websocket: WebSocket):
    ENDPOINT_URL_BASE = "wss://audio-streaming.us-virginia-1.direct.fireworks.ai"
    ENDPOINT_PATH = "/v1/audio/transcriptions/streaming"
    url_params = urllib.parse.urlencode({
        "language": "en",
        "authorization": f"Bearer {FIREWORKSAPIKEY}",
    })
    ENDPOINT_URL = f"{ENDPOINT_URL_BASE}{ENDPOINT_PATH}?{url_params}"
    print(f"Connecting to: {ENDPOINT_URL}")

    await websocket.accept()
    print("WebSocket connection accepted for transcription.")

    # Buffer for audio chunks
    audio_chunks = []
    transcript_segments = []
    ws_ready = threading.Event()

    def on_open(ws):
        print("Connected to Fireworks.ai transcription endpoint.")
        ws_ready.set()

    import queue
    transcript_queue = queue.Queue()

    def on_message(ws, message):
        #print("Received message from Fireworks.")
        response = json.loads(message)
        if "error" in response:
            print(response["error"])
        else:
            for s in response["segments"]:
                # append or update the transcript
                obj = {"id": s["id"], "text": s["text"]}
                #print(f"\tSegment: {obj}")
                transcript_queue.put(obj)

    def on_error(ws, error):
        print(f"Error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"Fireworks.ai WebSocket closed. Code: {close_status_code}, Message: {close_msg}")

    # Store the websocket client instance so we can send audio chunks directly
    fireworks_ws_client = {"ws": None}

    def run_fireworks_ws():
        print("Starting Fireworks WebSocket thread...")
        fw_ws = wsclient.WebSocketApp(
            ENDPOINT_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        fireworks_ws_client["ws"] = fw_ws
        fw_ws.run_forever()
        print("Fireworks WebSocket thread ended.")

    fw_thread = threading.Thread(target=run_fireworks_ws, daemon=True)
    fw_thread.start()
    ws_ready.wait(timeout=10)
    print("Fireworks WebSocket thread started and ready.")

    try:
        while True:
            # Check for transcript to send
            try:
                transcript = transcript_queue.get_nowait()
                #print(f"Sending transcript: {transcript}")
                await websocket.send_text(json.dumps(transcript))
            except queue.Empty:
                pass
            # Receive audio chunk
            try:
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.1)
                #print(f"Received audio chunk of length {len(data)} bytes.")
                fw_ws = fireworks_ws_client.get("ws")
                if fw_ws and fw_ws.sock and fw_ws.sock.connected:
                    #print("Sending audio chunk to Fireworks.ai websocket.")
                    fw_ws.send(data, opcode=wsclient.ABNF.OPCODE_BINARY)
                else:
                    print("Fireworks WebSocket not ready or not connected.")
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        print("WebSocket disconnected.")
        if fireworks_ws_client["ws"]:
            fireworks_ws_client["ws"].close()
    except Exception as e:
        print(f"WebSocket error: {e}")


@api_app.post("/summarize")
async def summarize(
    transcript: str = Form(...)
):
    """
    Summarize a transcript using Fireworks.ai or a placeholder model.
    """
    url = "https://api.fireworks.ai/inference/v1/chat/completions"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + FIREWORKSAPIKEY
    }
    data = {
        "model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "max_tokens": 4096,
        "top_p": 1,
        "top_k": 40,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "temperature": 0.6,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes transcripts. When a user provides a transcript, you will summarize it concisely and accurately."
            },
            {
                "role": "user",
                "content": f"{transcript}"
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        print("Summarizing transcript with Fireworks.ai...")
        if response.status_code == 200:
            result = response.json()
            #print(f"Response from Fireworks API: {json.dumps(result, indent=2)}")
            return result
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Summarization failed: {str(e)}')