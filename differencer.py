from PIL import Image

def get_pixel(diff_hash, prev_px, col, row):
    diff_hash <<= 1
    pixel = img.getpixel((col, row))
    diff_hash |= 1 * (pixel >= prev_px)

class Differencer:
    def __init__(self, image):
        self.image = image

    @property
    def _diff_hash(self):
        img = self.image.convert("L")
        img = img.resize((8, 8), Image.ANTIALIAS)
        prev_px = img.getpixel((0, 7))
        diff_hash = 0
        for row in range(0, 8, 2):
            for col in range(8):
                prev_px = get_pixel(diff_hash, prev_px, col, row)
            row += 1
            for col in range(7, -1, -1):
                prev_px = get_pixel(diff_hash, prev_px, col, row)
        return diff_hash

    def compare(self, other):
        return int(((64 - bin(mediaData[0] ^ int(mediaHash[0])).count('1'))*100.0)/64.0)
