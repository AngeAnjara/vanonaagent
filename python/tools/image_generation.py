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

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "batch_size": batch_size,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        url = "https://api.wavespeed.ai/v1/generate"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, headers=headers, json=payload)
                status = resp.status_code
                if status == 401:
                    raise RepairableException(
                        "WaveSpeed API error: 401 Unauthorized. Invalid API key."
                    )
                if status == 429:
                    raise RepairableException(
                        "WaveSpeed API error: 429 Rate limit exceeded. Try again later."
                    )
                if status >= 500:
                    raise RepairableException(
                        f"WaveSpeed API error: {status} Server error."
                    )
                if status != 200:
                    # include short body
                    text = resp.text[:500]
                    raise RepairableException(
                        f"WaveSpeed API error: {status} - {text}"
                    )

                data = resp.json()
        except RepairableException:
            raise
        except Exception as e:
            raise RepairableException(f"WaveSpeed API request failed: {type(e).__name__}: {e}")

        # Parse images; support either list of base64 strings or list of dicts with url/base64
        images: List[str] = []
        raw_images = data.get("images") if isinstance(data, dict) else None
        if isinstance(raw_images, list):
            for i, item in enumerate(raw_images):
                if isinstance(item, dict):
                    if item.get("base64"):
                        images.append(item["base64"])  # base64
                    elif item.get("url"):
                        images.append({"url": item["url"]})  # type: ignore
                elif isinstance(item, str):
                    # assume base64 string
                    images.append(item)

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
                "model": model,
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
