import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse

import aiohttp
from playwright.async_api import async_playwright

from toolkits.base import BaseToolkit


class WebEnhancedToolkit(BaseToolkit):
    """Web Enhanced Toolkit - Advanced web scraping and search"""

    name = "web_enhanced"
    description = "Web Enhanced - JS 渲染抓取、批量抓取、增强搜索、浏览器登录"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, ctx=None):
        super().__init__()
        ctx = ctx or {}
        self._cookies_dir = Path("/tmp/web_enhanced_cookies")
        self._cookies_dir.mkdir(parents=True, exist_ok=True)
        self._default_timeout = 30
        self._browser = None
        self._playwright = None

    def get_config_schema(self) -> dict:
        return {
            "cookies_dir": "Cookie 存储目录",
            "default_timeout": "默认超时秒数",
        }

    def get_tools(self):
        return [
            (self.web_fetch_js, "web_fetch_js",
             "用 Playwright 渲染 JS 后抓取页面内容，支持 CSS 选择器提取、等待元素、Cookie 登录。",
             [("url", "str", None, "目标 URL"),
              ("selector", "Optional[str]", None, "CSS 选择器，仅提取匹配元素"),
              ("wait_for", "Optional[str]", None, "等待指定选择器出现"),
              ("timeout", "int", 0, "超时秒数，0 用默认值 30"),
              ("extract_links", "bool", False, "是否同时提取页面链接"),
              ("extract_images", "bool", False, "是否同时提取页面图片链接"),
              ("cookies_file", "Optional[str]", None, "预先保存的 cookies 文件路径")]),
            (self.web_batch_fetch, "web_batch_fetch",
             "批量并发抓取多个 URL 的内容，比逐个抓取更高效。",
             [("urls", "str", None, "URL 列表，JSON 数组或逗号分隔"),
              ("timeout", "int", 0, "单个请求超时秒数"),
              ("max_concurrent", "int", 5, "最大并发数"),
              ("extract_text", "bool", True, "是否提取纯文本")]),
            (self.web_search_enhanced, "web_search_enhanced",
             "增强搜索：支持时间范围、站点限定、摘要提取。",
             [("query", "str", None, "搜索关键词"),
              ("num_results", "int", 10, "返回结果数量，最大 20"),
              ("time_range", "Optional[str]", None, "时间范围: day/week/month/year"),
              ("site", "Optional[str]", None, "限定站点域名"),
              ("extract_snippets", "bool", True, "是否提取摘要文本")]),
            (self.web_login, "web_login",
             "用 Playwright 浏览器自动登录网站并保存 cookies。",
             [("url", "str", None, "登录页面 URL"),
              ("username_selector", "str", None, "用户名输入框 CSS 选择器"),
              ("password_selector", "str", None, "密码输入框 CSS 选择器"),
              ("username", "str", None, "用户名/邮箱"),
              ("password", "str", None, "密码"),
              ("submit_selector", "Optional[str]", None, "提交按钮选择器"),
              ("cookies_file", "Optional[str]", None, "Cookie 保存路径"),
              ("wait_after_login", "int", 3, "登录后等待秒数"),
              ("verify_selector", "Optional[str]", None, "验证登录成功的选择器")]),
        ]

    async def _ensure_browser(self):
        if self._browser and self._browser.is_connected():
            self._lease("browser", 600, self._close_browser)
            return self._browser
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        self._lease("browser", 600, self._close_browser)
        return self._browser

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    @staticmethod
    def _extract_text(html: str, max_length: int = 50000) -> str:
        text = re.sub(
            r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r"<[^>]+>", " ", text)
        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )
        text = text.replace("&quot;", '"').replace("&#39;", "'")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_length]

    @staticmethod
    def _extract_links(html: str, base_url: str = "", limit: int = 100) -> list[dict]:
        links = []
        for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE):
            href = m.group(1)
            if href.startswith("#") or href.startswith("javascript:"):
                continue
            if base_url and href.startswith("/"):
                parsed = urlparse(base_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            after = html[m.end() : m.end() + 200]
            text_match = re.match(r"[^>]*>(.*?)</a>", after, re.IGNORECASE | re.DOTALL)
            text = (
                re.sub(r"<[^>]+>", "", text_match.group(1)).strip()
                if text_match
                else ""
            )
            links.append({"url": href, "text": text[:200]})
            if len(links) >= limit:
                break
        return links

    @staticmethod
    def _extract_title(html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""


    @staticmethod
    def _extract_images(html: str, base_url: str = "", limit: int = 100) -> list[dict]:
        images = []
        seen = set()
        img_tag_pat = re.compile(r'<img\s[^>]*>', re.IGNORECASE)
        alt_pat = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)
        
        for m in img_tag_pat.finditer(html):
            tag = m.group(0)
            
            alt_match = alt_pat.search(tag)
            alt = alt_match.group(1).strip() if alt_match else ""
            
            src = None
            src_type = "src"
            
            data_src_match = re.search(r'data-src=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if data_src_match:
                src = data_src_match.group(1)
                src_type = "data-src"
            
            if not src:
                src_match = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if src_match:
                    src = src_match.group(1)
                    src_type = "src"
            
            if not src:
                srcset_match = re.search(r'srcset=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if srcset_match:
                    srcset = srcset_match.group(1)
                    first_url = srcset.split(',')[0].strip().split()[0]
                    if first_url:
                        src = first_url
                        src_type = "srcset"
            
            if not src:
                continue
            
            if src.startswith("data:") or src.startswith("javascript:"):
                continue
            
            if base_url and src.startswith("/"):
                parsed = urlparse(base_url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            
            if src in seen:
                continue
            seen.add(src)
            
            img_info = {"src": src}
            if alt:
                img_info["alt"] = alt[:200]
            images.append(img_info)
            
            if len(images) >= limit:
                break
        return images

    async def web_fetch_js(
        self,
        url: str,
        selector: Optional[str] = None,
        wait_for: Optional[str] = None,
        timeout: int = 0,
        extract_links: bool = False,
        extract_images: bool = False,
        cookies_file: Optional[str] = None,
    ) -> dict:
        """Fetch page content after rendering JavaScript with Playwright.

        Args:
            url: Target URL
            selector: CSS selector to extract matching elements (optional)
            wait_for: Wait for specified selector to appear (optional)
            timeout: Timeout in seconds, 0 uses default
            extract_links: Whether to also extract page links
            extract_images: Whether to also extract page image links
            cookies_file: Path to pre-saved cookies file (optional)
        """
        timeout = timeout or self._default_timeout
        start = time.time()

        try:
            browser = await self._ensure_browser()
            context = await browser.new_context(
                user_agent=self.USER_AGENT,
                viewport={"width": 1920, "height": 1080},
            )

            if cookies_file:
                cpath = Path(cookies_file)
                if cpath.exists():
                    cookies = json.loads(cpath.read_text())
                    await context.add_cookies(cookies)

            page = await context.new_page()

            goto_kwargs = {"wait_until": "domcontentloaded", "timeout": timeout * 1000}
            response = await page.goto(url, **goto_kwargs)

            if wait_for:
                await page.wait_for_selector(wait_for, timeout=timeout * 1000)

            if selector:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        content = await element.inner_text()
                    else:
                        content = f"Selector '{selector}' not found"
                except Exception as e:
                    content = f"Selector error: {e}"
            else:
                content = await page.inner_text("body")

            title = await page.title()
            final_url = page.url

            links = []
            images = []
            html = ""
            if extract_links or extract_images:
                html = await page.content()
            if extract_links:
                links = self._extract_links(html, final_url)
            if extract_images:
                images = self._extract_images(html, final_url)

            status_code = response.status if response else None

            await context.close()

            return {
                "success": True,
                "url": final_url,
                "title": title,
                "status_code": status_code,
                "content": content[:50000],
                "links": links[:100] if extract_links else [],
                "images": images[:100] if extract_images else [],
                "duration_seconds": round(time.time() - start, 2),
            }

        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "duration_seconds": round(time.time() - start, 2),
            }

    async def web_batch_fetch(
        self,
        urls: str,
        timeout: int = 0,
        max_concurrent: int = 5,
        extract_text: bool = True,
    ) -> dict:
        """Batch fetch multiple URLs concurrently.

        Args:
            urls: JSON array string or comma-separated URL list
            timeout: Per-request timeout in seconds
            max_concurrent: Maximum concurrency
            extract_text: Whether to extract plain text (otherwise returns raw HTML)
        """
        timeout = timeout or self._default_timeout

        try:
            url_list = (
                json.loads(urls)
                if urls.startswith("[")
                else [u.strip() for u in urls.split(",") if u.strip()]
            )
        except json.JSONDecodeError:
            url_list = [u.strip() for u in urls.split(",") if u.strip()]

        if not url_list:
            return {"success": False, "error": "No valid URLs provided"}

        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_one(session: aiohttp.ClientSession, target_url: str) -> dict:
            async with semaphore:
                start = time.time()
                try:
                    async with session.get(
                        target_url,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        allow_redirects=True,
                    ) as resp:
                        html = await resp.text()
                        title = self._extract_title(html)
                        content = (
                            self._extract_text(html) if extract_text else html[:50000]
                        )
                        return {
                            "url": target_url,
                            "success": True,
                            "status_code": resp.status,
                            "title": title,
                            "content": content[:30000],
                            "duration_seconds": round(time.time() - start, 2),
                        }
                except Exception as e:
                    return {
                        "url": target_url,
                        "success": False,
                        "error": str(e),
                        "duration_seconds": round(time.time() - start, 2),
                    }

        start_all = time.time()
        async with aiohttp.ClientSession(
            headers={"User-Agent": self.USER_AGENT}
        ) as session:
            tasks = [fetch_one(session, u) for u in url_list]
            results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": True,
            "total": len(url_list),
            "succeeded": success_count,
            "failed": len(url_list) - success_count,
            "results": results,
            "duration_seconds": round(time.time() - start_all, 2),
        }

    async def web_search_enhanced(
        self,
        query: str,
        num_results: int = 10,
        time_range: Optional[str] = None,
        site: Optional[str] = None,
        extract_snippets: bool = True,
    ) -> dict:
        """Enhanced search with time range, site filtering, and auto-extracted snippets.

        Uses DuckDuckGo HTML version for searching, no API key required.

        Args:
            query: Search keywords
            num_results: Number of results to return (max 20)
            site: Limit to site domain (e.g. github.com)
            time_range: Time range, one of day/week/month/year
            extract_snippets: Whether to extract snippet text
        """
        num_results = min(num_results, 20)

        full_query = query
        if site:
            full_query += f" site:{site}"

        start = time.time()

        try:
            params = {"q": full_query, "kl": "wt-wt"}
            if time_range and time_range in ("day", "week", "month", "year"):
                params["df"] = time_range

            async with aiohttp.ClientSession(
                headers={"User-Agent": self.USER_AGENT}
            ) as session:
                async with session.get(
                    "https://html.duckduckgo.com/html/",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self._default_timeout),
                    allow_redirects=True,
                ) as resp:
                    if resp.status != 200:
                        return {
                            "success": False,
                            "error": f"Search returned status {resp.status}",
                        }

                    html = await resp.text()

            results = []
            blocks = re.findall(
                r'<div class="result__body">(.*?)</div>\s*</div>',
                html,
                re.DOTALL,
            )

            for block in blocks[:num_results]:
                title_m = re.search(
                    r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                    block,
                    re.DOTALL,
                )
                if not title_m:
                    continue
                raw_url = title_m.group(1)
                title = re.sub(r"<[^>]+>", "", title_m.group(2)).strip()

                url_match = re.search(r"uddg=([^&]+)", raw_url)
                actual_url = url_match.group(1) if url_match else raw_url

                snippet_m = re.search(
                    r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                    block,
                    re.DOTALL,
                )
                snippet = ""
                if snippet_m:
                    snippet = re.sub(r"<[^>]+>", "", snippet_m.group(1)).strip()

                results.append(
                    {
                        "title": title,
                        "url": actual_url,
                        "snippet": snippet[:500] if extract_snippets else "",
                    }
                )

            return {
                "success": True,
                "query": full_query,
                "time_range": time_range,
                "total_results": len(results),
                "results": results,
                "duration_seconds": round(time.time() - start, 2),
            }

        except Exception as e:
            return {
                "success": False,
                "query": full_query,
                "error": str(e),
                "duration_seconds": round(time.time() - start, 2),
            }

    async def web_login(
        self,
        url: str,
        username_selector: str,
        password_selector: str,
        username: str,
        password: str,
        submit_selector: Optional[str] = None,
        cookies_file: Optional[str] = None,
        wait_after_login: int = 3,
        verify_selector: Optional[str] = None,
    ) -> dict:
        """Log into a website using Playwright browser and save cookies.

        Args:
            url: Login page URL
            username_selector: CSS selector for username input
            password_selector: CSS selector for password input
            username: Username/email
            password: Password
            submit_selector: Submit button selector (optional, auto-submit with Enter)
            cookies_file: Cookie save path (optional, auto-generated by default)
            wait_after_login: Seconds to wait after login
            verify_selector: Selector for element verifying successful login (optional)
        """
        start = time.time()

        try:
            browser = await self._ensure_browser()
            context = await browser.new_context(
                user_agent=self.USER_AGENT,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            await page.goto(
                url, wait_until="domcontentloaded", timeout=self._default_timeout * 1000
            )

            await page.fill(username_selector, username)
            await page.fill(password_selector, password)

            if submit_selector:
                await page.click(submit_selector)
            else:
                await page.press(password_selector, "Enter")

            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(wait_after_login)

            login_verified = False
            if verify_selector:
                try:
                    el = await page.query_selector(verify_selector)
                    login_verified = el is not None
                except Exception:
                    login_verified = False

            cookies = await context.cookies()
            if not cookies_file:
                domain = urlparse(url).netloc.replace(".", "_").replace(":", "_")
                cookies_file = str(self._cookies_dir / f"{domain}_cookies.json")

            Path(cookies_file).parent.mkdir(parents=True, exist_ok=True)
            Path(cookies_file).write_text(json.dumps(cookies, indent=2))

            final_url = page.url
            title = await page.title()

            await context.close()

            return {
                "success": True,
                "url": url,
                "final_url": final_url,
                "title": title,
                "cookies_file": cookies_file,
                "cookies_count": len(cookies),
                "login_verified": login_verified,
                "duration_seconds": round(time.time() - start, 2),
            }

        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "duration_seconds": round(time.time() - start, 2),
            }
