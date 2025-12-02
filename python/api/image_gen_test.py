import httpx
from flask import Request, Response

from python.helpers.api import ApiHandler
from python.helpers import settings
from python.helpers.print_style import PrintStyle


class ImageGenTest(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            current = settings.get_settings()

            api_key = input.get("apiKey") or current.get("image_gen_api_key", "")
            model = input.get("model") or current.get("image_gen_model", "bytedance/seedream-v4")

            if not api_key:
                return {"success": False, "message": "Missing API key"}

            MODEL_MAPPING = {
                "seedance": "bytedance/seedream-v4",
                "nanobanana": "google/gemini-2.5-flash-image/text-to-image",
            }
            mapped = MODEL_MAPPING.get(model, model)

            submit_url = f"https://api.wavespeed.ai/api/v3/{mapped}"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {"prompt": "test", "width": 512, "height": 512, "steps": 10, "batch_size": 1}

            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.post(submit_url, headers=headers, json=payload)
                    status = resp.status_code
                    if status == 401:
                        return {"success": False, "message": "Invalid API key. Please check your credentials."}
                    if status == 404:
                        return {"success": False, "message": "Invalid model or endpoint. Please check model name."}
                    if status == 429:
                        return {"success": False, "message": "Rate limit exceeded. Try again later."}
                    if status >= 500:
                        return {"success": False, "message": f"Server error from WaveSpeed ({status}). Try again later."}
                    if status != 200:
                        short = resp.text[:400]
                        return {"success": False, "message": f"Error: {status} - {short}"}

                    data = resp.json()
                    request_id = data.get("requestId") or data.get("id")
                    if not request_id:
                        return {"success": False, "message": "No requestId returned by WaveSpeed."}

                    # single quick poll
                    poll_url = f"https://api.wavespeed.ai/api/v3/predictions/{request_id}/result"
                    poll = await client.get(poll_url, headers=headers)
                    if poll.status_code in (200, 202):
                        return {
                            "success": True,
                            "message": f"WaveSpeed connection successful. Model: {mapped}",
                            "available_models": [
                                "bytedance/seedream-v4",
                                "google/gemini-2.5-flash-image/text-to-image",
                            ],
                        }
                    else:
                        return {"success": False, "message": f"Polling failed: {poll.status_code}"}
            except Exception as net_err:
                try:
                    PrintStyle.error(f"WaveSpeed test request failed: {type(net_err).__name__}: {net_err}")
                except Exception:
                    pass
                return {"success": False, "message": f"Network error: {type(net_err).__name__}: {net_err}"}
        except Exception as e:
            try:
                PrintStyle.error(f"ImageGenTest error: {type(e).__name__}: {e}")
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Unexpected error: {type(e).__name__}: {e}",
            }
