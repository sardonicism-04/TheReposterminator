from PIL import Image

def diff_hash(image):
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
        return diff_hash

