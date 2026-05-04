"""
Web Enhanced 工具包 - 高级网页抓取与搜索

提供四个工具：
- web_fetch_js: 用 Playwright 渲染 JS 后抓取页面内容
- web_batch_fetch: 批量并发抓取多个 URL
- web_search_enhanced: 增强搜索（支持时间/站点过滤、结果提取）
- web_login: 浏览器登录并保存 cookies
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse

import aiohttp
from playwright.async_api import async_playwright

from .base import BaseToolkit


class WebEnhancedToolkit(BaseToolkit):
    """Web Enhanced 工具包 - 高级网页抓取与搜索"""

    name = "web_enhanced"
    description = "Web Enhanced - JS 渲染抓取、批量抓取、增强搜索、浏览器登录"

    # 默认 User-Agent
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, cookies_dir: str = "", default_timeout: int = 30):
        self._cookies_dir = (
            Path(cookies_dir) if cookies_dir else Path("/tmp/web_enhanced_cookies")
        )
        self._cookies_dir.mkdir(parents=True, exist_ok=True)
        self._default_timeout = default_timeout
        self._browser = None
        self._playwright = None

    def get_config_schema(self) -> dict:
        return {
            "cookies_dir": "Cookie 存储目录",
            "default_timeout": "默认超时秒数",
        }

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    async def _ensure_browser(self):
        """确保 Playwright 浏览器实例可用"""
        if self._browser and self._browser.is_connected():
            return self._browser
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        return self._browser

    async def _close_browser(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    # ------------------------------------------------------------------
    # Helper: extract clean text from page
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(html: str, max_length: int = 50000) -> str:
        """从 HTML 中提取可读文本（轻量级，不依赖 bs4）"""
        # Remove script/style
        text = re.sub(
            r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        # Remove tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Clean entities
        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )
        text = text.replace("&quot;", '"').replace("&#39;", "'")
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_length]

    @staticmethod
    def _extract_links(html: str, base_url: str = "", limit: int = 100) -> list[dict]:
        """提取页面中的链接"""
        links = []
        for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE):
            href = m.group(1)
            if href.startswith("#") or href.startswith("javascript:"):
                continue
            if base_url and href.startswith("/"):
                parsed = urlparse(base_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            # Extract link text (rough)
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

    # ------------------------------------------------------------------
    # Tool: web_fetch_js
    # ------------------------------------------------------------------

    async def web_fetch_js(
        self,
        url: str,
        selector: Optional[str] = None,
        wait_for: Optional[str] = None,
        timeout: int = 0,
        extract_links: bool = False,
        cookies_file: Optional[str] = None,
    ) -> dict:
        """用 Playwright 渲染 JS 后抓取页面内容。

        Args:
            url: 目标 URL
            selector: CSS 选择器，仅提取匹配元素（可选）
            wait_for: 等待指定选择器出现（可选）
            timeout: 超时秒数，0 用默认值
            extract_links: 是否同时提取页面链接
            cookies_file: 预先保存的 cookies 文件路径（可选）
        """
        timeout = timeout or self._default_timeout
        start = time.time()

        try:
            browser = await self._ensure_browser()
            context = await browser.new_context(
                user_agent=self.USER_AGENT,
                viewport={"width": 1920, "height": 1080},
            )

            # Load cookies if provided
            if cookies_file:
                cpath = Path(cookies_file)
                if cpath.exists():
                    cookies = json.loads(cpath.read_text())
                    await context.add_cookies(cookies)

            page = await context.new_page()

            # Navigate
            goto_kwargs = {"wait_until": "domcontentloaded", "timeout": timeout * 1000}
            response = await page.goto(url, **goto_kwargs)

            # Wait for selector if specified
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=timeout * 1000)

            # Extract content
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
            if extract_links:
                html = await page.content()
                links = self._extract_links(html, final_url)

            status_code = response.status if response else None

            await context.close()

            return {
                "success": True,
                "url": final_url,
                "title": title,
                "status_code": status_code,
                "content": content[:50000],
                "links": links[:100] if extract_links else [],
                "duration_seconds": round(time.time() - start, 2),
            }

        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "duration_seconds": round(time.time() - start, 2),
            }

    # ------------------------------------------------------------------
    # Tool: web_batch_fetch
    # ------------------------------------------------------------------

    async def web_batch_fetch(
        self,
        urls: str,
        timeout: int = 0,
        max_concurrent: int = 5,
        extract_text: bool = True,
    ) -> dict:
        """批量并发抓取多个 URL。

        Args:
            urls: JSON 数组字符串或逗号分隔的 URL 列表
            timeout: 单个请求超时秒数
            max_concurrent: 最大并发数
            extract_text: 是否提取纯文本（否则返回原始 HTML 片段）
        """
        timeout = timeout or self._default_timeout

        # Parse URLs
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

    # ------------------------------------------------------------------
    # Tool: web_search_enhanced
    # ------------------------------------------------------------------

    async def web_search_enhanced(
        self,
        query: str,
        num_results: int = 10,
        time_range: Optional[str] = None,
        site: Optional[str] = None,
        extract_snippets: bool = True,
    ) -> dict:
        """增强搜索：支持时间范围、站点过滤、自动提取摘要。

        通过 DuckDuckGo HTML 版进行搜索，无需 API key。

        Args:
            query: 搜索关键词
            num_results: 返回结果数量（最多 20）
            site: 限定站点域名（如 github.com）
            time_range: 时间范围，可选 day/week/month/year
            extract_snippets: 是否提取摘要文本
        """
        num_results = min(num_results, 20)

        # Build search query
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

            # Parse DuckDuckGo HTML results
            results = []
            # DDG result blocks: <div class="result__body">
            blocks = re.findall(
                r'<div class="result__body">(.*?)</div>\s*</div>',
                html,
                re.DOTALL,
            )

            for block in blocks[:num_results]:
                # Title & URL
                title_m = re.search(
                    r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                    block,
                    re.DOTALL,
                )
                if not title_m:
                    continue
                raw_url = title_m.group(1)
                title = re.sub(r"<[^>]+>", "", title_m.group(2)).strip()

                # DDG uses redirect URL, extract actual URL
                url_match = re.search(r"uddg=([^&]+)", raw_url)
                actual_url = url_match.group(1) if url_match else raw_url

                # Snippet
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

    # ------------------------------------------------------------------
    # Tool: web_login
    # ------------------------------------------------------------------

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
        """用 Playwright 浏览器登录网站并保存 cookies。

        Args:
            url: 登录页面 URL
            username_selector: 用户名输入框 CSS 选择器
            password_selector: 密码输入框 CSS 选择器
            username: 用户名/邮箱
            password: 密码
            submit_selector: 提交按钮选择器（可选，自动回车提交）
            cookies_file: Cookies 保存路径（可选，默认自动生成）
            wait_after_login: 登录后等待秒数
            verify_selector: 登录成功后验证元素选择器（可选）
        """
        start = time.time()

        try:
            browser = await self._ensure_browser()
            context = await browser.new_context(
                user_agent=self.USER_AGENT,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            # Navigate to login page
            await page.goto(
                url, wait_until="domcontentloaded", timeout=self._default_timeout * 1000
            )

            # Fill credentials
            await page.fill(username_selector, username)
            await page.fill(password_selector, password)

            # Submit
            if submit_selector:
                await page.click(submit_selector)
            else:
                await page.press(password_selector, "Enter")

            # Wait for navigation / element
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(wait_after_login)

            # Verify if selector provided
            login_verified = False
            if verify_selector:
                try:
                    el = await page.query_selector(verify_selector)
                    login_verified = el is not None
                except Exception:
                    login_verified = False

            # Save cookies
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
