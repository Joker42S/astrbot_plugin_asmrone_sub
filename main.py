from typing import List, Dict

import aiofiles
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.api.event import MessageChain

import asyncio
from .asmrone import AsmroneClient
from pathlib import Path
import json
import aiohttp

class AsmroneSub(Star):
    def __init__(self, context: Context, config : dict):
        super().__init__(context)
        self.config = config
        self.context = context
        self.sub_check_task = None
    
    async def initialize(self):
        self.plugin_name = 'astrbot_plugin_asmrone_sub'
        self.check_interval = self.config.get("check_interval", 360)
        max_page = self.config.get("max_page", 2)
        self.base_url = self.config.get("base_url", "https://asmr-200.com")
        self.api_url = self.config.get("api_url", "https://api.asmr-200.com")
        self.base_dir = StarTools.get_data_dir(self.plugin_name)
        self.temp_dir = self.base_dir / "temp"
        if not self.temp_dir.exists():
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.sub_sources_file : Path = self.base_dir / "sub_sources.json"
        self.search_tags = self.config.get("search_tags", None)
        self.proxy = self.config.get("proxy", "")
        self.asmrone = AsmroneClient(
            base_url=self.base_url,
            api_url=self.api_url,
            max_page=max_page,
            latest_id_file=str(self.base_dir/"latest_id.txt"),
            search_tags=self.search_tags or [],
            proxy=self.proxy)
        self.sub_check_task = asyncio.create_task(self.start())

    async def start(self):
        while(True):
            await asyncio.sleep(self.check_interval * 60)
            try:
                await self._refresh_sub()
            except Exception as e:
                logger.error(f"刷新订阅时发生错误: {e}")

    @filter.command("订阅ASMR")
    async def add_sub(self, event: AstrMessageEvent):
        new_source = event.unified_msg_origin
        sources = self._load_sub_sources()
        if new_source in sources:
            yield event.plain_result("已订阅，无需重复订阅")
            return
        sources.append(new_source)
        await self._save_sub_sources(sources)
        yield event.plain_result("订阅成功")

    @filter.command("刷新ASMR")
    async def refresh_sub(self, event: AstrMessageEvent):
        await self._refresh_sub()
        yield event.plain_result("刷新完成")

    async def _refresh_sub(self):
        sources = self._load_sub_sources()
        if not sources or len(sources) == 0:
            logger.info("无订阅源，无需刷新")
            return
        new_articles : List[Dict] = await self.asmrone.fetch_latest_articles()
        if len(new_articles) > 0:
            msg = MessageChain().message(f"ASMR.one更新了{len(new_articles)}个新作品。\n")
            for source in sources:
                await self.context.send_message(source, msg)
        async with aiohttp.ClientSession() as session:
            for article in new_articles:
                title = article.get("title", "无标题")
                # url = article.get("url", "")
                desc = article.get("desc", "")
                cover = article.get("cover", "")
                source_id = article.get("source_id", "")
                msg = MessageChain().message(f"【{source_id}】\n【标题】：{title}\n{desc}\n")
                img_file = await self._download_single_image(cover, article["id"], session)
                if img_file is None:
                    img_msg = MessageChain().message("封面图片下载失败")
                else:
                    img_msg = MessageChain().file_image(str(img_file))
                for source in sources:
                    try:
                        await self.context.send_message(source, msg)
                        await self.context.send_message(source, img_msg)
                    except Exception as e:
                        logger.error(f"发送消息到{source}时失败：{e}")
        
    def _load_sub_sources(self):
        if not Path.exists(self.sub_sources_file):
            return []
        with open(str(self.sub_sources_file), "r", encoding="utf-8") as f:
            return json.load(f)
        
    async def _save_sub_sources(self, sources):
        with open(str(self.sub_sources_file), "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=4)

    async def _download_single_image(self, url: str, id: int, session = None, modify_hash = True) -> Path | None:
        """下载单张图片"""
        for file_extension in ['jpg', 'png', 'jpeg']:
            file_path = self.temp_dir / f"{id}.{file_extension}"
            if file_path.exists():
                ## 图片已存在，无需重复下载
                return file_path
        try:
            # 设置请求头
            headers = {            
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            }
            if not session:
                raise ValueError("无法建立连接，session未提供")
            # 下载图片
            async with session.get(url, headers=headers, timeout=30, proxy=self.proxy) as response:
                if response.status == 200:
                    # Determine file extension from content type
                    # content_type = response.headers.get('content-type', '')
                    # if 'jpeg' in content_type or 'jpg' in content_type:
                    #     file_extension = 'jpg'
                    # elif 'png' in content_type:
                    #     file_extension = 'png'
                    # else:
                    #     # Get extension from URL
                    #     file_extension = url.split('.')[-1].split('?')[0]
                    #     if file_extension not in ['jpg', 'jpeg', 'png']:
                    #         file_extension = 'jpg'  # Default to jpg
                    
                    # file_path = self.temp_dir / f"{id}.{file_extension}"
                    file_path = self.temp_dir / f"{id}.jpg"
                    
                    img_data = await response.read()
                    if modify_hash:
                        img_data = await _image_obfus(img_data)
                    async with aiofiles.open(file_path, 'wb') as f:
                        await f.write(img_data)
                    
                    logger.info(f"下载图片 {id}: {file_path}")
                    return file_path
                else:
                    logger.error(f"下载图片失败，状态码: {response.status}")
                    return None
            
        except Exception as e:
            logger.error(f"下载封面图片失败: {e}")
            return None
        
    async def terminate(self):
        if self.sub_check_task and not self.sub_check_task.done():
            self.sub_check_task.cancel()
            try:
                await self.sub_check_task
            except asyncio.CancelledError:
                logger.info(
                    "asmrone sub task was successfully cancelled during terminate."
                )
            except Exception as e:
                logger.error(
                    f"Error awaiting cancellation of asmrone sub task: {e}"
                )

async def _image_obfus(img_data):
    """破坏图片哈希"""
    from PIL import Image as ImageP
    from io import BytesIO
    import random

    try:
        with BytesIO(img_data) as input_buffer:
            with ImageP.open(input_buffer) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")

                width, height = img.size
                pixels = img.load()

                points = []
                for _ in range(3):
                    while True:
                        x = random.randint(0, width - 1)
                        y = random.randint(0, height - 1)
                        if (x, y) not in points:
                            points.append((x, y))
                            break

                for x, y in points:
                    r, g, b = pixels[x, y]

                    r_change = random.choice([-1, 1])
                    g_change = random.choice([-1, 1])
                    b_change = random.choice([-1, 1])

                    new_r = max(0, min(255, r + r_change))
                    new_g = max(0, min(255, g + g_change))
                    new_b = max(0, min(255, b + b_change))

                    pixels[x, y] = (new_r, new_g, new_b)

                with BytesIO() as output:
                    img.save(output, format="JPEG", quality=95, subsampling=0)
                    return output.getvalue()

    except Exception as e:
        logger.warning(f"破坏图片哈希时发生错误: {str(e)}")
        return img_data
    