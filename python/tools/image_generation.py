import asyncio
import base64
import json
import time
from typing import Any, List

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.errors import RepairableException
from python.helpers.print_style import PrintStyle
from python.helpers import files


class ImageGeneration(Tool):
    # Map legacy names to official model paths
    MODEL_MAPPING: dict[str, str] = {
        "seedance": "bytedance/seedream-v4",
        "nanobanana": "google/gemini-2.5-flash-image/text-to-image",
        "bytedance/seedream-v4": "bytedance/seedream-v4",
        "google/gemini-2.5-flash-image/text-to-image": "google/gemini-2.5-flash-image/text-to-image",
    }
    async def before_execution(self, **kwargs):
        await super().before_execution(**kwargs)
        try:
            PrintStyle(font_color="#1B4F72").print(
                f"Preparing WaveSpeed generation using model '{self.agent.config.image_gen_model}'"
            )
        except Exception:
            pass

    async def after_execution(self, response: Response, **kwargs):
        try:
            add = response.additional or {}
            n = len(add.get("images", []))
            PrintStyle(font_color="#1B4F72").print(
                f"WaveSpeed generation finished with {n} image(s)."
            )
        except Exception:
            pass
        await super().after_execution(response, **kwargs)

    async def execute(self, **kwargs) -> Response:
        if not self.agent.config.image_gen_enabled:
            raise RepairableException(
                "WaveSpeed image generation is disabled. Enable it in Settings > Image Generation."
            )

        prompt: str = (kwargs.get("prompt") or self.args.get("prompt") or "").strip()
        if not prompt:
            raise RepairableException("Missing required argument: prompt")

        negative_prompt: str | None = (
            kwargs.get("negative_prompt") or self.args.get("negative_prompt")
        )
        width = int(
            kwargs.get("width")
            or self.args.get("width")
            or self.agent.config.image_gen_default_width
        )
        height = int(
            kwargs.get("height")
            or self.args.get("height")
            or self.agent.config.image_gen_default_height
        )
        steps = int(
            kwargs.get("steps")
            or self.args.get("steps")
            or self.agent.config.image_gen_default_steps
        )
        batch_size = int(
            kwargs.get("batch_size")
            or self.args.get("batch_size")
            or self.agent.config.image_gen_batch_size
        )
        batch_size = max(1, min(5, batch_size))

        model = (
            kwargs.get("model")
            or self.args.get("model")
            or self.agent.config.image_gen_model
        )
        api_key = (
            kwargs.get("api_key")
            or self.args.get("api_key")
            or self.agent.config.image_gen_api_key
        )
        if not api_key:
            raise RepairableException(
                "Missing WaveSpeed API key. Add it in Settings > Image Generation or pass api_key."
            )

        # Map model and construct task-based API
        mapped_model = self.MODEL_MAPPING.get(model, model)
        submit_url = f"https://api.wavespeed.ai/api/v3/{mapped_model}"
        result_base = "https://api.wavespeed.ai/api/v3/predictions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        submit_payload: dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "batch_size": batch_size,
        }
        if negative_prompt:
            submit_payload["negative_prompt"] = negative_prompt

        # Submit task
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(submit_url, headers=headers, json=submit_payload)
                status = resp.status_code
                if status == 401:
                    raise RepairableException("WaveSpeed API error: 401 Unauthorized. Invalid API key.")
                if status == 404:
                    raise RepairableException("WaveSpeed API error: 404 Not Found. Invalid model or endpoint.")
                if status == 429:
                    raise RepairableException("WaveSpeed API error: 429 Rate limit exceeded. Try again later.")
                if status >= 500:
                    raise RepairableException(f"WaveSpeed API error: {status} Server error.")
                if status != 200:
                    text = resp.text[:500]
                    raise RepairableException(f"WaveSpeed API error: {status} - {text}")
                submit_data = resp.json()
        except RepairableException:
            raise
        except Exception as e:
            raise RepairableException(f"WaveSpeed API submit failed: {type(e).__name__}: {e}")

        request_id = (submit_data or {}).get("requestId") or (submit_data or {}).get("id")
        if not request_id:
            raise RepairableException("WaveSpeed API error: Missing requestId in submit response.")
        try:
            PrintStyle.info(f"WaveSpeed task submitted. requestId={request_id}")
        except Exception:
            pass

        # Poll for result
        poll_url = f"{result_base}/{request_id}/result"
        deadline = time.time() + 120  # 120s timeout
        images_payload: Any = None
        last_status = ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                while time.time() < deadline:
                    r = await client.get(poll_url, headers=headers)
                    if r.status_code == 404:
                        raise RepairableException("WaveSpeed API error: 404 result not found. Check requestId.")
                    if r.status_code == 401:
                        raise RepairableException("WaveSpeed API error: 401 Unauthorized during polling.")
                    if 400 <= r.status_code < 500:
                        # Any other client error should not be retried; report immediately
                        short = r.text[:500]
                        raise RepairableException(
                            f"WaveSpeed API error: {r.status_code} Client error during polling - {short}"
                        )
                    if r.status_code >= 500:
                        # transient server error: wait and retry
                        await asyncio.sleep(3)
                        continue
                    # treat 200 as valid payload regardless of status content
                    data = r.json()
                    status = str(data.get("status", "")).lower()
                    last_status = status or last_status
                    if status in ("completed", "succeeded", "success", "done"):
                        images_payload = data
                        break
                    if status in ("failed", "error"):
                        err = data.get("error") or data.get("message") or "Generation failed"
                        raise RepairableException(f"WaveSpeed task failed: {err}")
                    # not done yet
                    try:
                        PrintStyle().print("Waiting for WaveSpeed generation...")
                    except Exception:
                        pass
                    await asyncio.sleep(3)
        except RepairableException:
            raise
        except Exception as e:
            raise RepairableException(f"WaveSpeed polling failed: {type(e).__name__}: {e}")

        if images_payload is None:
            raise RepairableException(f"WaveSpeed generation timeout (last status: {last_status or 'unknown'}).")

        # Extract images from v3 payload structure
        images: List[Any] = []
        # Try common keys: data.images, images, output
        if isinstance(images_payload, dict):
            maybe_images = (
                (images_payload.get("data") or {}).get("images")
                if isinstance(images_payload.get("data"), dict)
                else None
            ) or images_payload.get("images") or images_payload.get("output")
            if isinstance(maybe_images, list):
                images = maybe_images

        # Fail fast if no images are returned by the provider
        if not images:
            raise RepairableException(
                f"WaveSpeed API returned no images for completed task (model: {mapped_model})."
            )

        saved_paths: List[str] = []
        ts = int(time.time())
        out_dir = "outputs/images"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                for idx, item in enumerate(images):
                    fname = files.safe_file_name(
                        f"generated_image_{ts}_{idx+1}.png"
                    )
                    rel_path = f"{out_dir}/{fname}"
                    if isinstance(item, dict) and item.get("url"):
                        try:
                            r = await client.get(item["url"])  # type: ignore
                            r.raise_for_status()
                            files.write_file_bin(rel_path, r.content)
                            saved_paths.append(rel_path)
                        except Exception as dl_err:
                            PrintStyle.error(
                                f"Failed to download image {idx+1} from URL: {dl_err}"
                            )
                    elif isinstance(item, str):
                        try:
                            files.write_file_base64(rel_path, item)
                            saved_paths.append(rel_path)
                        except Exception as wr_err:
                            PrintStyle.error(
                                f"Failed to write base64 image {idx+1}: {wr_err}"
                            )
        except Exception as e:
            raise RepairableException(
                f"Failed to persist generated images: {type(e).__name__}: {e}"
            )

        additional = {
            "images": saved_paths,
            "meta": {
                "model": mapped_model,
                "width": width,
                "height": height,
                "steps": steps,
                "batch_size": batch_size,
                "negative_prompt": negative_prompt or "",
            },
        }

        message_obj = {
            "message": "WaveSpeed generation successful.",
            "images": saved_paths,
            "meta": additional["meta"],
        }
        message = json.dumps(message_obj, indent=2)
        return Response(message=message, break_loop=True, additional=additional)
