import unittest
from unittest.mock import patch
from PIL import Image
import artwork
import widget

class ArtworkTests(unittest.TestCase):
    def test_panel_has_transparent_corners_and_reference_center(self):
        im = artwork.panel((498,184),28,'#eab8a4')
        self.assertEqual(im.getpixel((0,0))[3],0)
        self.assertEqual(im.getpixel((249,92)),(29,33,38,255))
    def test_progress_is_continuous_and_clamped(self):
        a=artwork.progress((300,8),0.501,'#eab8a4')
        b=artwork.progress((300,8),0.55,'#eab8a4')
        self.assertNotEqual(a.tobytes(),b.tobytes())
        self.assertEqual(artwork.progress((300,8),2,'#eab8a4').tobytes(),artwork.progress((300,8),1,'#eab8a4').tobytes())
    def test_real_position_microseconds(self):
        with patch.object(widget,'controllable_player',return_value='spotify'), patch.object(widget,'run',side_effect=['50','200000000']):
            self.assertEqual(widget.progress_fraction(),.25)
    def test_missing_position_is_not_fake_progress(self):
        with patch.object(widget,'controllable_player',return_value=None):
            self.assertIsNone(widget.progress_fraction())
    def test_icons_have_alpha(self):
        for kind in ('previous','next','play','pause','cloud','sun','rain','storm','fog','offline','battery','charging'):
            im=artwork.icon(kind)
            self.assertEqual(im.mode,'RGBA')
            self.assertEqual(im.getpixel((0,0))[3],0)

if __name__=='__main__': unittest.main()
