#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from astrbot.api import logger

import asyncio
import aiohttp
from urllib.parse import quote
import os
from typing import Optional, List, Dict

class AsmroneClient:
    def __init__(
        self,
        api_url: str = "https://api.asmr-200.com/",
        base_url: str = "https://asmr-200.com/",
        latest_id_file: str = "",
        max_page: int = 2,
        retry: int = 3,
        retry_delay: float = 1.0,
        search_tags: List[str] = [],
        proxy: str | None = None,
    ):
        """
        :param base_url: 网站地址
        :param latest_id_file: 储存最新作品id的文件路径
        :param max_page: 正常抓取时最多抓取多少页
        :param retry: 网络请求失败后的重试次数
        :param retry_delay: 重试的初始等待时间（指数退避）
        :param search_tags: 搜索条件列表
        :param proxy: 代理服务器
        """
        self.base_url = base_url.rstrip("/")
        self.api_url = api_url.rstrip("/")
        self.latest_id_file = latest_id_file
        self.max_page = max_page
        self.retry = retry
        self.retry_delay = retry_delay
        self.search_tags = search_tags
        self.search_pattern = " ".join(search_tags)
        self.proxy = proxy
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }

    # -------------------- 工具区 --------------------
    def _load_latest_id(self) -> Optional[int]:
        if not os.path.exists(self.latest_id_file):
            return None
        try:
            with open(self.latest_id_file, "r") as f:
                return int(f.read().strip())
        except:
            return None

    def _save_latest_id(self, id_val: int):
        with open(self.latest_id_file, "w") as f:
            f.write(str(id_val))

    async def search_asmr_async(self,
        pattern: str = "",
        domain: str = "https://api.asmr-200.com",
        order: str = "create_date",
        sort: str = "desc",
        page: int = 1,
        subtitle: int = 0,
        include_translation_works: bool = True,
        timeout: float = 30.0,
        proxy: str | None = None,
        retries: int = 3,
        retry_delay: float = 5.0,
    ):
        """
        异步搜索 ASMR-200 API，并带自动重试。
        
        参数:
            pattern: 搜索关键词
            domain: API 域名
            order: 排序字段
            sort: 排序方向
            page: 页码
            subtitle: 字幕筛选 0/1
            include_translation_works: 是否包含翻译作品
            timeout: 单次请求超时
            proxy: 代理
            retries: 最大重试次数
            retry_delay: 每次重试等待秒数
        """

        encoded_pattern = quote(pattern)

        url = (
            f"{domain}/api/search/{encoded_pattern}"
            f"?order={order}"
            f"&sort={sort}"
            f"&page={page}"
            f"&subtitle={subtitle}"
            f"&includeTranslationWorks={str(include_translation_works).lower()}"
        )

        for attempt in range(1, retries + 1):
            try:
                timeout_config = aiohttp.ClientTimeout(total=timeout)

                async with aiohttp.ClientSession(timeout=timeout_config) as session:
                    async with session.get(url, proxy=proxy) as resp:
                        resp.raise_for_status()
                        return await resp.json()

            except Exception as e:
                if attempt >= retries:
                    raise  # 尝试次数已用完，抛出异常
                
                # 等待后重试
                await asyncio.sleep(retry_delay)
    
    def _parse_work_data(self, data):
        #解析单个作品的json数据，返回Dict{title: str, url: str, id: int, cover: str, desc: str}
        res = {
            "title": data.get("title", "无标题"),
            "url": f"{self.base_url}/work/{data.get('id', 0)}",
            "id": data.get("id", 0),
            "cover": data.get("mainCoverUrl", None),
            "desc": f"社团：{data.get('name', '未知')}, CV: {' '.join(cv['name'] for cv in data.get('vas'))}"
        }
        return res

    async def fetch_latest_articles(self) -> List[Dict]:
        #返回数据格式: [{"title": str, "url": str, "id": int, "cover": str, "desc": str}, ...]
        logger.info("开始检查ASMR.one更新...")
        latest_id = self._load_latest_id() or 0
        results = []
        new_id = 0

        async with aiohttp.ClientSession() as session:
            not_more_latest_work = False
            for page_index in range(1, self.max_page + 1):
                if not_more_latest_work:
                    break
                logger.info(f"\n获取第 {page_index} 页的音声：")
                fetch_res = await self.search_asmr_async(page=page_index, pattern=self.search_pattern, domain=self.api_url, proxy=self.proxy)
                if not fetch_res or not fetch_res.get("works", None):
                    logger.error("获取网站数据失败")
                    return results
                works = fetch_res["works"]
                if len(works) == 0:
                    if page_index == 1:
                        logger.error("搜索结果为空，请检查搜索条件")
                    else:
                        logger.info("当前页无更多搜索结果，停止")
                    break
                
                for art in works:
                    #parse data, id title url cover desc(vas name)
                    meta_data = self._parse_work_data(art)
                    id_val = meta_data["id"]
                    if new_id == 0:
                        new_id = id_val
                    if id_val == latest_id:
                        logger.info("已到达上次更新位置，停止")
                        not_more_latest_work = True
                        break
                    results.append(meta_data)
                    if latest_id == 0:
                        logger.info(f"首次更新，推送最新一个作品的id并记录：{id_val}")
                        latest_id = id_val
                        not_more_latest_work = True
                        break
                    logger.info(f"发现新作品：{id_val}")

                await asyncio.sleep(3)

            if new_id != 0:
                self._save_latest_id(new_id)

        return results