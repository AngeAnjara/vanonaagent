import json
from typing import Any

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
            model = input.get("model") or current.get("image_gen_model", "seedance")

            if not api_key:
                return {"success": False, "message": "Missing API key"}

            # Build a small test payload
            payload: dict[str, Any] = {
                "model": model,
                "prompt": "test",
                "width": 512,
                "height": 512,
                "steps": 10,
                "batch_size": 1,
            }

            url = "https://api.wavespeed.ai/v1/generate"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    status = resp.status_code

                    if status == 200:
                        return {
                            "success": True,
                            "message": f"WaveSpeed connection successful. Model: {model}",
                            "available_models": ["seedance", "nanobanana"],
                        }
                    elif status == 401:
                        return {
                            "success": False,
                            "message": "Invalid API key. Please check your credentials.",
                        }
                    elif status == 429:
                        return {
                            "success": False,
                            "message": "Rate limit exceeded. Try again later.",
                        }
                    elif status >= 500:
                        return {
                            "success": False,
                            "message": f"Server error from WaveSpeed ({status}). Try again later.",
                        }
                    else:
                        short = resp.text[:400]
                        return {
                            "success": False,
                            "message": f"Error: {status} - {short}",
                        }
            except Exception as net_err:
                try:
                    PrintStyle.error(f"WaveSpeed test request failed: {type(net_err).__name__}: {net_err}")
                except Exception:
                    pass
                return {
                    "success": False,
                    "message": f"Network error: {type(net_err).__name__}: {net_err}",
                }
        except Exception as e:
            try:
                PrintStyle.error(f"ImageGenTest error: {type(e).__name__}: {e}")
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Unexpected error: {type(e).__name__}: {e}",
            }
