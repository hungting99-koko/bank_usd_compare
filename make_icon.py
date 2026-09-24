"""One-off script: generates app_icon.ico (green coin with a $ sign) for the exe."""
from PIL import Image, ImageDraw, ImageFont

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Coin body: green circle with a darker rim so it reads as "money" at a glance
margin = 8
draw.ellipse([margin, margin, SIZE - margin, SIZE - margin], fill=(21, 128, 61, 255), outline=(13, 82, 39, 255), width=10)
inner = 26
draw.ellipse([inner, inner, SIZE - inner, SIZE - inner], outline=(255, 255, 255, 255), width=6)

# Dollar sign, centered
text = "$"
font = None
for font_name in ("segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
    try:
        font = ImageFont.truetype(font_name, 150)
        break
    except OSError:
        continue
if font is None:
    font = ImageFont.load_default()

bbox = draw.textbbox((0, 0), text, font=font)
w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
draw.text(((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1]), text, font=font, fill=(255, 255, 255, 255))

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save("app_icon.ico", sizes=sizes)
print("saved app_icon.ico")
