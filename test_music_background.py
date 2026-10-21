import unittest
from PIL import Image
import music_background

class MusicBackgroundTest(unittest.TestCase):
    def test_full_bleed_rounded_and_readable(self):
        image = music_background.compose(Image.new('RGB', (640,640), 'white'))
        self.assertEqual(image.size, (498,498))
        self.assertEqual(image.getpixel((0,0))[3], 0)
        self.assertGreater(image.getpixel((25,90))[0], image.getpixel((300,420))[0])
        self.assertLess(image.getpixel((300,420))[0], 100)
        self.assertEqual(image.getpixel((25,90))[3], 255)
