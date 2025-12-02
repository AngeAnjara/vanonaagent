import asyncio
import json
import time
from typing import Any

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import RepairableException
from python.helpers import files


class HtmlDesign(Tool):
    async def execute(self, **kwargs) -> Response:
        await self.agent.handle_intervention()

        if not getattr(self.agent.config, "ppt_enabled", False):
            raise RepairableException(
                "PowerPoint generation is disabled. Enable in Settings > PowerPoint & PDF Generation."
            )

        content: str = (kwargs.get("content") or self.args.get("content") or "").strip()
        if not content:
            raise RepairableException("Missing required argument: content")

        theme: str = (kwargs.get("theme") or self.args.get("theme") or self.agent.config.ppt_default_theme).strip()
        colors = kwargs.get("colors") or self.args.get("colors") or []
        chart_type = (kwargs.get("chart_type") or self.args.get("chart_type") or "").strip()
        chart_data = kwargs.get("chart_data") or self.args.get("chart_data") or {}

        # Theme -> palette mapping (fallback if no explicit colors provided)
        theme_palettes = {
            "modern": ["#111827", "#2563EB", "#10B981", "#F59E0B"],
            "corporate": ["#1F2937", "#0EA5E9", "#64748B", "#0F766E"],
            "creative": ["#0F172A", "#A855F7", "#EF4444", "#22C55E"],
            "minimal": ["#111827", "#6B7280", "#D1D5DB", "#10B981"],
        }
        resolved_colors = colors if colors else theme_palettes.get(theme.lower(), theme_palettes["modern"])  # type: ignore[index]
        palette = {
            "primary": resolved_colors[0] if len(resolved_colors) > 0 else "#111827",
            "accent": resolved_colors[1] if len(resolved_colors) > 1 else "#2563EB",
            "muted": resolved_colors[2] if len(resolved_colors) > 2 else "#6B7280",
            "highlight": resolved_colors[3] if len(resolved_colors) > 3 else "#10B981",
            "all": resolved_colors,
        }

        # Build system prompt for utility LLM
        system_prompt = (
            "Generate a complete HTML document with embedded CSS for a presentation. "
            f"Theme: {theme}. Palette: {palette}. Content: {content}. "
            "Use responsive design, modern typography, and clear sections per slide. "
            "Include placeholders for charts when applicable (canvas with id per slide). Output only valid HTML."
        )

        user_prompt = content

        try:
            html_base = await self.agent.call_utility_model(system=system_prompt, message=user_prompt, background=True)
        except Exception as e:
            raise RepairableException(f"Utility model failed to generate HTML: {type(e).__name__}: {e}")

        if not isinstance(html_base, str) or "<html" not in html_base.lower():
            # Fallback minimal document if LLM returned incomplete content
            html_base = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>AI Presentation</title>
  <style>
    :root {{ --c1: {colors[0] if colors else '#3498db'}; --c2: {colors[1] if len(colors)>1 else '#2ecc71'}; }}
    body {{ font-family: Inter, system-ui, Arial, sans-serif; margin:0; background:#fafafa; color:#222; }}
    .slide {{ width: 1280px; height: 720px; margin: 24px auto; background:#fff; box-shadow:0 10px 30px rgba(0,0,0,.08); border-radius:16px; padding:48px; box-sizing:border-box; }}
    h1,h2,h3 {{ margin:0 0 12px; }}
    .title {{ color: var(--c1); font-weight:800; }}
    .accent {{ color: var(--c2); }}
    .grid {{ display:grid; gap:12px; }}
    .chart-wrap {{ margin-top:24px; }}
  </style>
</head>
<body>
  <div class=\"slide\">
    <h1 class=\"title\">Presentation</h1>
    <p>{content}</p>
    <div class=\"chart-wrap\">{('<canvas id="chart1"></canvas>') if chart_type else ''}</div>
  </div>
</body>
</html>
"""

        # Inject chart library if requested
        chart_lib = getattr(self.agent.config, "ppt_chart_library", "chartjs")
        if chart_type:
            if chart_lib == "chartjs":
                default_chart_data = {"labels": [], "datasets": [{"data": []}]}
                data_json = json.dumps(chart_data or default_chart_data)
                chart_kind = chart_type or "bar"
                injection = (
                    "<script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>\n"
                    "<script>\n"
                    "document.addEventListener('DOMContentLoaded',()=>{\n"
                    "  const ctx=document.getElementById('chart1'); if(!ctx) return;\n"
                    f"  const data={data_json};\n"
                    f"  new Chart(ctx, {{ type: '{chart_kind}', data, options: {{ responsive:true, maintainAspectRatio:false }} }});\n"
                    "});\n"
                    "</script>\n"
                )
                html = html_base.replace("</body>", injection + "</body>")
            elif chart_lib == "plotly":
                default_plotly_data = {"type": "bar", "x": [], "y": []}
                plotly_json = json.dumps(chart_data or default_plotly_data)
                injection = (
                    "<script src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></script>\n"
                    "<div id=\"chart1\" style=\"width:100%;height:380px\"></div>\n"
                    "<script>\n"
                    "document.addEventListener('DOMContentLoaded',()=>{\n"
                    f"  const data=[{plotly_json}];\n"
                    "  Plotly.newPlot('chart1', data, {margin:{t:24}});\n"
                    "});\n"
                    "</script>\n"
                )
                html = html_base.replace("<div class=\"chart-wrap\"></div>", injection).replace("</body>", "</body>")
            elif chart_lib == "matplotlib":
                # For matplotlib, expect a base64 image provided or leave placeholder
                html = html_base  # keep as-is; conversion tool may render chart differently
            else:
                html = html_base
        else:
            html = html_base

        out_dir = files.get_abs_path("outputs", "presentations")
        try:
            files.ensure_directory(out_dir)
        except Exception:
            pass
        path = files.get_abs_path("outputs", "presentations", f"design_{int(time.time())}.html")
        try:
            files.write_file(path, html)
        except Exception as e:
            raise RepairableException(f"Failed to write HTML file: {type(e).__name__}: {e}")

        preview = bool(getattr(self.agent.config, "ppt_enable_preview", True))
        msg = json.dumps({"html_path": path, "theme": theme, "palette": palette, "preview_enabled": preview})
        return Response(message=msg, break_loop=False, additional={"html_path": path, "palette": palette})
