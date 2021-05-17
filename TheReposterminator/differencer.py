"""
TheReposterminator Reddit bot to detect reposts
Copyright (C) 2021 sardonicism-04

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
from PIL import Image


def generate_hash(image):
    img = image.convert("L")
    img = img.resize((8, 8), Image.ANTIALIAS)
    pixels = [*img.getdata()]
    prev_px = pixels[0]
    diff_hash = 0

    for pixel in pixels:
        diff_hash <<= 1
        diff_hash |= int(pixel >= prev_px)
        prev_px = pixel

    return diff_hash


def compare_hashes(hash1, hash2):
    hash1 = int(hash1)
    hash2 = int(hash2)
    return int(((64 - bin(hash1 ^ hash2).count("1")) * 100.0) / 64.0)


# This is the legacy hash generation algorithm
# It is only still here in the event that the new
# algorithm proves to be inferior. If the new
# algorithm works without issue, this will be removed.

# def diff_hash(image):
#     """Generates a difference hash from an image"""
#     img = image.convert("L")
#     img = img.resize((8, 8), Image.ANTIALIAS)
#     prev_px = img.getpixel((0, 7))
#     diff_hash = 0

#     for row in range(0, 8, 2):
#         for col in range(8):

#             diff_hash <<= 1
#             pixel = img.getpixel((col, row))
#             diff_hash |= int(pixel >= prev_px)
#             prev_px = pixel
#         row += 1

#         for col in range(7, -1, -1):
#             diff_hash <<= 1
#             pixel = img.getpixel((col, row))
#             diff_hash |= int(pixel >= prev_px)
#             prev_px = pixel

#     return diff_hash
