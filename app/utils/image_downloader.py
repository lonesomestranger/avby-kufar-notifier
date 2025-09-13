import logging

from aiogram.types import BufferedInputFile
from curl_cffi.requests import AsyncSession


async def download_image_to_bytes(url: str) -> bytes | None:
    try:
        async with AsyncSession(impersonate="chrome136") as session:
            headers = {"referer": "https://cars.av.by/"}
            response = await session.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logging.error(f"Error downloading image bytes from {url}: {e}")
        return None


async def download_image_to_buffer(url: str) -> BufferedInputFile | None:
    image_bytes = await download_image_to_bytes(url)
    if image_bytes:
        return BufferedInputFile(image_bytes, filename="photo.jpg")
    return None
