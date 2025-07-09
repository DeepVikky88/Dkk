import asyncio
import glob
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Union
import requests
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from youtubesearchpython.__future__ import VideosSearch
import base64
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
            raise FileNotFoundError("No .txt files found in the specified folder.")
        cookie_txt_file = random.choice(txt_files)
        with open(filename, 'a') as file:
            file.write(f'Choosen File : {cookie_txt_file}\n')
        return f"cookies/{os.path.basename(cookie_txt_file)}"
    except:
        return None

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz and "unavailable videos are hidden" not in errorz.decode("utf-8").lower():
        return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def _get_video_details(self, link: str, limit: int = 10) -> Union[dict, None]:
        try:
            results = VideosSearch(link, limit=limit)
            for result in (await results.next()).get("result", []):
                duration_str = result.get("duration", "0:00")
                duration_secs = time_to_seconds(duration_str)
                if duration_secs > 3600:  # Skip videos longer than 1 hour
                    continue
                return result
            return None
        except Exception as e:
            logger.error(f"Error in _get_video_details: {str(e)}")
            return None

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1, message_1.reply_to_message] if message_1.reply_to_message else [message_1]
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        return (message.text or message.caption)[entity.offset:entity.offset + entity.length]
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0].split("?si=")[0]
        result = await self._get_video_details(link)
        if not result:
            raise ValueError("No suitable audio found (duration > 1 hour or unavailable)")
        return (
            result["title"],
            result["duration"],
            time_to_seconds(result["duration"]),
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"]
        )

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0].split("?si=")[0]
        result = await self._get_video_details(link)
        if not result:
            raise ValueError("No suitable audio found")
        return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0].split("?si=")[0]
        result = await self._get_video_details(link)
        if not result:
            raise ValueError("No suitable audio found")
        return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0].split("?si=")[0]
        result = await self._get_video_details(link)
        if not result:
            raise ValueError("No suitable audio found")
        return result["thumbnails"][0]["url"].split("?")[0]

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        link = link.split("&")[0].split("?si=")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        result = [x for x in playlist.split("\n") if x]
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0].split("?si=")[0]
        result = await self._get_video_details(link)
        if not result:
            raise ValueError("No suitable audio found")
        return {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result["duration"],
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }, result["id"]

    async def download(self, link: str, mystic, videoid: Union[bool, str] = None) -> str:
        if videoid:
            vid_id = link
            link = self.base + link
        else:
            vid_id = (await self.details(link))[4]  # Extract video ID from details

        loop = asyncio.get_running_loop()

        def create_session():
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=0.1)
            session.mount('http://', HTTPAdapter(max_retries=retries))
            session.mount('https://', HTTPAdapter(max_retries=retries))
            return session

        def audio_dl(vid_id):
            try:
                if not YT_API_KEY or not YTPROXY:
                    logger.error("API KEY or YTPROXY_URL not set in config")
                    return None
                headers = {"x-api-key": YT_API_KEY, "User-Agent": "Mozilla/5"}
                xyz = os.path.join("downloads", f"{vid_id}.mp3")
                if os.path.exists(xyz):
                    return xyz
                getAudio = requests.get(f"{YTPROXY}/audio/{vid_id}", headers=headers, timeout=60)
                songData = getAudio.json()
                if songData.get('status') != 'success':
                    logger.error(f"API error: {songData.get('message', 'Unknown error')}")
                    return None
                audio_url = base64.b64decode(songData['audio_url']).decode()
                ydl_opts = {
                    "outtmpl": xyz,
                    "quiet": True,
                    "xff": "IN",
                    "nocheckcertificate": True,
                    "cookiefile": cookie_txt_file(),
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }]
                }
                with ThreadPoolExecutor(max_workers=4) as executor:
                    future = executor.submit(lambda: yt_dlp.YoutubeDL(ydl_opts).download([audio_url]))
                    future.result()
                return xyz
            except Exception as e:
                logger.error(f"Error downloading audio: {str(e)}")
                return None

        downloaded_file = await loop.run_in_executor(None, lambda: audio_dl(vid_id))
        if not downloaded_file:
            raise ValueError("Failed to download audio")
        return downloaded_file, True
