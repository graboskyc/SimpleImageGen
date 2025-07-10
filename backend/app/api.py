from fastapi import FastAPI, Response, File, UploadFile, HTTPException, Form
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
    prompt: str = Form("A beautiful sunset over the ocean")
):
    url = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-kontext-pro"

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FIREWORKSAPIKEY}",
        }

        data = {
            "prompt": prompt
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
