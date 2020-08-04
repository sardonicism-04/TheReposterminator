"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2020 sardonicism-04

TheReposterminator is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

TheReposterminator is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with TheReposterminator.  If not, see <https://www.gnu.org/licenses/>.
"""
import asyncio
import io

from PIL import Image

def _diff_hash(raw_bytes):
    """Generates a difference hash from an image"""
    BytesIO_object = io.BytesIO(raw_bytes)
    image = Image.open(BytesIO_object)
    img = image.convert("L")
    img = img.resize((8, 8), Image.ANTIALIAS)
    prev_px = img.getpixel((0, 7))
    diff_hash = 0
    for row in range(0, 8, 2):
        for col in range(8):
            diff_hash <<= 1
            pixel = img.getpixel((col, row))
            diff_hash |= 1 * (pixel >= prev_px)
            prev_px = pixel
        row += 1
        for col in range(7, -1, -1):
            diff_hash <<= 1
            pixel = img.getpixel((col, row))
            diff_hash |= 1 * (pixel >= prev_px)
            prev_px = pixel
    BytesIO_object.close()
    img.close()
    return diff_hash

async def diff_hash(raw_bytes):
    """Handles the asynchronous interfacing for creating difference hashes"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _diff_hash, raw_bytes)

