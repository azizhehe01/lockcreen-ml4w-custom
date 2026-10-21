"""Full-bleed live cover with a readable right-hand text area."""
from PIL import Image, ImageDraw, ImageOps
import artwork


def compose(cover):
    size = (498, 498)
    image = ImageOps.fit(cover.convert('RGB'), size, method=Image.Resampling.LANCZOS).convert('RGBA')
    shade = Image.new('RGBA', size)
    draw = ImageDraw.Draw(shade)
    for y in range(size[1]):
        alpha = round(215 * min(1, max(0, (y-210)/180)))
        draw.line((0,y,size[0],y), fill=(14,18,23,alpha))
    image = Image.alpha_composite(image, shade)
    mask = Image.new('L', (996,996))
    ImageDraw.Draw(mask).rounded_rectangle((0,0,995,995),radius=56,fill=255)
    image.putalpha(mask.resize(size, Image.Resampling.LANCZOS))
    ImageDraw.Draw(image).rounded_rectangle((1,1,496,496),radius=27,outline='#f5c6a7',width=2)
    return image


def current():
    import widget
    with Image.open(widget.cover()) as cover:
        return artwork.save(compose(cover), 'music-background')


if __name__ == '__main__':
    print(current())
