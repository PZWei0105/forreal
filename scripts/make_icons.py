"""產生 App 圖示：牌桌綠墊上一枚全像「真」印（和 App 裡標示已證實消息的印同一個）。"""
import pathlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = pathlib.Path(__file__).resolve().parent.parent / 'site' / 'icons'
FONT = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
MAT_TOP, MAT_BOT = (20, 58, 49), (10, 34, 29)
INK = (15, 31, 26)
HOLO = [(127, 243, 226), (169, 156, 255), (255, 163, 211), (255, 227, 143), (143, 240, 201)]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def holo(size):
    im = Image.new('RGB', (size, size))
    px = im.load()
    n = len(HOLO) - 1
    for y in range(size):
        for x in range(size):
            t = ((x * 0.82 + y * 0.45) / (size * 1.27)) % 1
            k = min(int(t * n), n - 1)
            px[x, y] = lerp(HOLO[k], HOLO[k + 1], t * n - k)
    return im


def draw(size, maskable=False):
    S = 1024
    im = Image.new('RGB', (S, S))
    d = ImageDraw.Draw(im)
    for y in range(S):
        d.line([(0, y), (S, y)], fill=lerp(MAT_TOP, MAT_BOT, y / S))
    grid = Image.new('L', (S, S), 0)
    gd = ImageDraw.Draw(grid)
    for k in range(0, S, 64):
        gd.line([(k, 0), (k, S)], fill=22, width=3)
        gd.line([(0, k), (S, k)], fill=22, width=3)
    im = Image.composite(Image.new('RGB', (S, S), (200, 255, 235)), im, grid)
    scale = 0.56 if maskable else 0.72
    w = int(S * scale)
    x0 = (S - w) // 2
    # 陰影
    sh = Image.new('L', (S, S), 0)
    ImageDraw.Draw(sh).rounded_rectangle([x0, x0 + 26, x0 + w, x0 + w + 26], radius=int(w * 0.2), fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(38))
    im = Image.composite(Image.new('RGB', (S, S), (3, 14, 11)), im, sh)
    # 全像印面
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([x0, x0, x0 + w, x0 + w], radius=int(w * 0.2), fill=255)
    face = Image.new('RGB', (S, S))
    face.paste(holo(w), (x0, x0))
    im = Image.composite(face, im, mask)
    d = ImageDraw.Draw(im)
    inset = int(w * 0.055)
    d.rounded_rectangle([x0 + inset, x0 + inset, x0 + w - inset, x0 + w - inset], radius=int(w * 0.16),
                        outline=(255, 255, 255), width=max(6, int(w * 0.022)))
    font = ImageFont.truetype(FONT, int(w * 0.66), index=3)  # TC
    bbox = d.textbbox((0, 0), '真', font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((S / 2 - tw / 2 - bbox[0], S / 2 - th / 2 - bbox[1]), '真', font=font, fill=INK)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    draw(512).save(OUT / 'icon-512.png', optimize=True)
    draw(192).save(OUT / 'icon-192.png', optimize=True)
    draw(512, maskable=True).save(OUT / 'icon-maskable-512.png', optimize=True)
    draw(180).save(OUT / 'apple-touch-icon.png', optimize=True)
    draw(32).save(OUT / 'favicon-32.png', optimize=True)
    print('icons ok')
