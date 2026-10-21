import copy
import re
import tomllib
import unittest
from pathlib import Path
import render

class Presets(unittest.TestCase):
    def test_all_sizes_scale_content_without_changing_center_widgets(self):
        settings = tomllib.loads(render.SETTINGS.read_text())
        wallpaper = Path(Path(settings['appearance']['wallpaper_file']).expanduser().read_text().strip())
        original = copy.deepcopy(settings)
        results = {}
        for preset, factor in [('big',1),('medium',.8),('small',.65)]:
            settings['widgets'] = {'size':preset}
            text = render.render(settings,(1920,1080),wallpaper)
            blocks = re.findall(r'(image|label|input-field) \{([^}]+)\}',text)
            music = next(b for k,b in blocks if 'music-background-' in b)
            self.assertIn(f'size = {round(498*factor)}\n', music)
            title = next(b for k,b in blocks if 'widget.py music\n' in b)
            self.assertIn(f'font_size = {round(17*factor)}\n',title)
            controls = [b for k,b in blocks if 'onclick =' in b]
            self.assertEqual(len(controls),3)
            for b in controls: self.assertIn(f'size = {round(54*factor)}\n',b)
            results[preset] = [b for k,b in blocks if 'date +%H:%M' in b or k == 'input-field']
        self.assertEqual(results['big'],results['small'])
        self.assertEqual(settings['music'],original['music'])
        settings['widgets']['size'] = 'tiny'
        with self.assertRaisesRegex(ValueError,'widgets.size'):
            render.render(settings,(1920,1080),wallpaper)
