from flask import Request, Response

from python.helpers.api import ApiHandler
from python.helpers.print_style import PrintStyle


class PptTest(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            missing_libs = []
            available_libs = []

            # Test python-pptx
            try:
                import pptx  # type: ignore
                available_libs.append("python-pptx")
            except ImportError:
                missing_libs.append("python-pptx (pip install python-pptx)")

            # Test weasyprint
            try:
                import weasyprint  # type: ignore
                available_libs.append("weasyprint")
            except ImportError:
                missing_libs.append("weasyprint (pip install weasyprint)")

            # Test BeautifulSoup
            try:
                from bs4 import BeautifulSoup  # type: ignore
                available_libs.append("beautifulsoup4")
            except ImportError:
                missing_libs.append("beautifulsoup4 (pip install beautifulsoup4)")

            # Test Playwright (package + browser installation)
            playwright_missing = False
            browser_missing = False
            try:
                from playwright.async_api import async_playwright  # type: ignore
            except ImportError:
                playwright_missing = True
            if playwright_missing:
                missing_libs.append("playwright (pip install playwright)")
            else:
                try:
                    async def _probe():
                        async with async_playwright() as p:  # type: ignore
                            browser = await p.chromium.launch()
                            await browser.close()
                    # In async context, simply await the probe
                    await _probe()
                    available_libs.append("playwright (chromium installed)")
                except Exception:
                    browser_missing = True
            if browser_missing:
                missing_libs.append("playwright browsers not installed (run: playwright install)")

            if missing_libs:
                return {
                    "success": False,
                    "message": f"Missing libraries: {', '.join(missing_libs)}",
                    "available": available_libs,
                    "missing": missing_libs,
                }
            else:
                return {
                    "success": True,
                    "message": f"All libraries available: {', '.join(available_libs)}",
                    "available": available_libs,
                    "missing": [],
                }
        except Exception as e:
            try:
                PrintStyle.error(f"PptTest error: {type(e).__name__}: {e}")
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Unexpected error: {type(e).__name__}: {e}",
            }
