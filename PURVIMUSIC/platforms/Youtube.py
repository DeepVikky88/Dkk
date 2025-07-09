import asyncio
import os
import random
import aiohttp
import yt_dlp

# API configuration
API_URL = "https://tgapi.xbitcode.com"
API_KEY = "xbit_0000557970017716954481"

def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        raise FileNotFoundError("No cookie files found in the cookies directory")
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file

async def YouTubeAPI(link: str):
    def extract_video_id(link: str) -> str:
        try:
            if "v=" not in link:
                raise ValueError("Invalid YouTube URL: 'v=' not found")
            video_id = link.split('v=')[-1].split('&')[0]
            if not video_id or len(video_id) != 11:  # YouTube video IDs are typically 11 characters
                raise ValueError(f"Invalid video ID: {video_id}")
            return video_id
        except Exception as e:
            print(f"Error extracting video ID: {e}")
            return None

    video_id = extract_video_id(link)
    if not video_id:
        print("Failed to extract valid video ID")
        return None

    # Try API first
    song_url = f"{API_URL}/song/{video_id}?api={API_KEY}"
    print(f"Calling API: {song_url}")
    async with aiohttp.ClientSession() as session:
        for attempt in range(10):
            try:
                async with session.get(song_url) as response:
                    print(f"API response status: {response.status}")
                    if response.status == 404:
                        print("API endpoint not found. Check API_URL or endpoint configuration.")
                        break
                    if response.status != 200:
                        raise Exception(f"API request failed with status code {response.status}")

                    try:
                        data = await response.json()
                    except aiohttp.ContentTypeError:
                        print("API response is not valid JSON")
                        break

                    print(f"API response data: {data}")
                    status = data.get("status", "").lower()

                    if status == "done":
                        download_url = data.get("link")
                        if not download_url:
                            raise Exception("API response did not provide a download URL.")
                        break
                    elif status == "downloading":
                        print(f"Attempt {attempt + 1}: Still downloading, retrying...")
                        await asyncio.sleep(4)
                    else:
                        error_msg = data.get("error") or data.get("message") or f"Unexpected status '{status}'"
                        raise Exception(f"API error: {error_msg}")
            except Exception as e:
                print(f"[FAIL] Attempt {attempt + 1}: {e}")
                # Fallback to yt-dlp after one API failure
                print("Falling back to yt-dlp")
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": f"downloads/{video_id}.%(ext)s",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(link, download=True)
                        return os.path.join("downloads", f"{info['id']}.mp3")
                except Exception as e:
                    print(f"yt-dlp download failed: {e}")
                    return None
        else:
            print("⏱️ Max retries reached. Still downloading...")
            return None

        try:
            file_format = data.get("format", "mp3")
            file_extension = file_format.lower()
            file_name = f"{video_id}.{file_extension}"
            download_folder = "downloads"
            os.makedirs(download_folder, exist_ok=True)
            file_path = os.path.join(download_folder, file_name)
            print(f"Downloading to: {file_path}")

            async with session.get(download_url) as file_response:
                if file_response.status != 200:
                    raise Exception(f"Failed to download file: HTTP {file_response.status}")
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await file_response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                print(f"Successfully downloaded: {file_path}")
                return file_path
        except Exception as e:
            print(f"Error occurred while downloading song: {e}")
            # Fallback to yt-dlp if download fails
            print("Download failed, falling back to yt-dlp")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"downloads/{video_id}.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    return os.path.join("downloads", f"{info['id']}.mp3")
            except Exception as e:
                print(f"yt-dlp download failed: {e}")
                return None
    return None
