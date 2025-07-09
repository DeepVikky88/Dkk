import asyncio
import glob
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Union
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from PURVIMUSIC import LOGGER
from PURVIMUSIC.utils.formatters import time_to_seconds
from config import YT_API_KEY, YTPROXY_URL as YTPROXY

logger = LOGGER(__name__)

def cookie_txt_file():
    try:
        folder_path = f"{os.getcwd()}/cookies"
        filename = f"{os.getcwd()}/cookies/logs.csv"
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        if not txt_files:
            raise FileNotFoundError("No .txt files found.")
        cookie_file = random.choice(txt_files)
        with open(filename, 'a') as file:
            file.write(f'Choosen File: {cookie_file}\n')
        return f"cookies/{cookie_file.split('/')[-1]}"
    except:
        return None

async def check_file_size(link):
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "--cookies", cookie_txt_file(), "-J", link,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error(f"Error checking file size: {stderr.decode()}")
        return None
    info = json.loads(stdout.decode())
    return sum(f.get('filesize', 0) for f in info.get('formats', []))

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return err.decode() if err else out.decode()

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"

    async def _get_video_details(self, link: str, limit: int = 1) -> dict:
        try:
            results = VideosSearch(link, limit=limit)
            for result in (await results.next()).get("result", []):
                duration_str = result.get("duration", "0:00")
                duration_secs = sum(int(p) * 60 ** i for i, p in enumerate(reversed(duration_str.split(":"))))
                if duration_secs <= 3600:  # Skip videos longer than 1 hour
                    return result
            raise ValueError("No suitable video found (duration > 1 hour or unavailable)")
        except Exception as e:
            logger.error(f"Error fetching video details: {str(e)}")
            raise

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        for msg in [message, message.reply_to_message] if message.reply_to_message else [message]:
            for entity in (msg.entities or []) + (msg.caption_entities or []):
                if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
                    return entity.url if entity.type == MessageEntityType.TEXT_LINK else (msg.text or msg.caption)[entity.offset:entity.offset + entity.length]
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None) -> tuple:
        if videoid:
            link = self.base + link
        link = link.split("&")[0].split("?si=")[0]
        result = await self._get_video_details(link)
        duration_sec = time_to_seconds(result["duration"]) if result["duration"] else 0
        return result["title"], result["duration"], duration_sec, result["thumbnails"][0]["url"].split("?")[0], result["id"]

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        return (await self._get_video_details(link.split("&")[0].split("?si=")[0]))["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        return (await self._get_video_details(link.split("&")[0].split("?si=")[0]))["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        return (await self._get_video_details(link.split("&")[0].split("?si=")[0]))["thumbnails"][0]["url"].split("?")[0]

    async def track(self, link: str, videoid: Union[bool, str] = None) -> tuple:
        if videoid:
            link = self.base + link
        link = link.split("&")[0].split("?si=")[0]
        result = await self._get_video_details(link)
        track_details = {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result["duration"],
            "thumb": result["thumbnails"][0]["url"].split("?")[0]
        }
        return TQtrack_details, result["id"]

    async def download(self, link: str, mystic, videoid: Union[bool, str] = None) -> str:
        if videoid:
            vid_id = link
            link = self.base + link
        else:
            vid_id = link.split("=")[-1].split("&")[0].split("?si=")[0]

        async def audio_dl(vid_id: str) -> str:
            if not YT_API_KEY or not YTPROXY:
                logger.error("YT_API_KEY or YTPROXY_URL not set in config.")
                return ""
            xyz = os.path.join("downloads", f"{vid_id}.mp3")
            if os.path.exists(xyz):
                return xyz
            session = Session()
            session.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.1)))
            try:
                headers = {"x-api-key": YT_API_KEY, "User-Agent": "Mozilla/5.0"}
                response = session.get(f"{YTPROXY}/audio/{vid_id}", headers=headers, timeout=60).json()
                if response.get('status') == 'success':
                    audio_url = base64.b64decode(response['audio_url']).decode()
                    ydl_opts = {
                        "format": "bestaudio[ext=mp3]/bestaudio",
                        "outtmpl": xyz,
                        "quiet": True,
                        "cookiefile": cookie_txt_file(),
                        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
                    }
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        executor.submit(lambda: yt_dlp.YoutubeDL(ydl_opts).download([audio_url])).result()
                    return xyz
                logger.error(f"API error: {response.get('message', 'Unknown error')}")
                return ""
            except Exception as e:
                logger.error(f"Download error: {str(e)}")
                return ""

        return await asyncio.get_running_loop().run_in_executor(None, lambda: audio_dl(vid_id))
