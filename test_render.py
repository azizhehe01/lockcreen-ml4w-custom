import importlib.util
from pathlib import Path
import re
import tomllib
import unittest
from unittest.mock import patch, Mock

P = Path(__file__).parent
spec = importlib.util.spec_from_file_location('render', P / 'render.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LayoutRegression(unittest.TestCase):
    def setUp(self):
        self.settings = tomllib.loads((P / 'settings.toml').read_text())
        self.settings['widgets'] = {'size': 'big'}
        self.wallpaper = Path((Path.home() / '.cache/ml4w/hyprland-dotfiles/current_wallpaper').read_text().strip())
        settings = {k: v.copy() for k, v in self.settings.items()}
        settings['music']['enabled'] = True
        self.conf = module.render(settings, (1920, 1080), self.wallpaper)
        self.blocks = re.findall(r'(label|shape|input-field|background|image) \{([^}]+)\}', self.conf)

    def test_disabled_music_keeps_weather_but_renders_no_music(self):
        settings = {k: v.copy() for k, v in self.settings.items()}
        settings['music']['enabled'] = False
        conf = module.render(settings, (1920, 1080), self.wallpaper)
        self.assertNotIn('lockscreen-cover.png', conf)
        self.assertNotIn('control-play-pause', conf)
        self.assertNotIn('widget.py music', conf)
        self.assertIn('widget.py weather', conf)
        self.assertIn('widget.py battery', conf)

    def test_spacious_music_controls_and_panel_palette(self):
        self.assertEqual(self.conf.count('onclick ='), 3)
        self.assertIn('size = 498', self.conf)
        self.assertIn('size = 138', self.conf)
        self.assertNotIn('color = rgba(171c20e8)', self.conf)
        self.assertIn('music-background-', self.conf)
        for widget in ('weather-temp', 'weather-condition', 'battery-status', 'battery-bar-image', 'battery-image', 'music-progress-image'):
            self.assertIn('widget.py ' + widget, self.conf)

    def test_foreground_labels_above_panels(self):
        for kind, body in self.blocks:
            if kind == 'label':
                self.assertIn('zindex = 3', body)
            if kind == 'shape':
                self.assertIn('zindex = ' + ('2' if 'onclick =' in body else '1'), body)

    def test_only_password_is_bar_below_avatar(self):
        self.assertEqual(sum(k == 'input-field' for k, _ in self.blocks), 1)
        self.assertEqual(sum(k == 'shape' and 'size = 370, 38' in b for k, b in self.blocks), 0)

    def test_avatar_uses_safe_cache_path_and_music_controls(self):
        settings = {k: v.copy() for k, v in self.settings.items()}
        settings['avatar']['image'] = '/dummy/path/avatar.png'
        with patch.object(module, 'prepare_avatar', return_value=Path.home() / '.cache/ml4w/lockscreen-avatar.png'):
            conf = module.render(settings, (1920, 1080), self.wallpaper)
        images = [b for k, b in re.findall(r'(label|shape|input-field|background|image) \{([^}]+)\}', conf) if k == 'image']
        self.assertTrue(any('path = ' + str(Path.home() / '.cache/ml4w/lockscreen-avatar.png') in b for b in images))
        self.assertFalse(any('Downloads' in b for b in images))
        labels = [b for k, b in self.blocks if k == 'image']
        for action in ('previous', 'play-pause', 'next'):
            self.assertTrue(any('onclick = python3 ' in b and 'control-' + action in b for b in labels))
        self.assertIn('font_family = Fira Sans', self.conf)
        self.assertIn('font_family = Source Code Pro', self.conf)

    def test_control_targets_active_player_without_touching_live_playback(self):
        widget_spec = importlib.util.spec_from_file_location('widget', P / 'widget.py')
        widget = importlib.util.module_from_spec(widget_spec)
        widget_spec.loader.exec_module(widget)
        for action, expected in [('control-previous', 'previous'), ('control-play-pause', 'play-pause'), ('control-next', 'next')]:
            with patch.object(widget, 'current_player', return_value='spotify'), patch.object(widget.subprocess, 'run', return_value=Mock(returncode=0)) as called:
                self.assertTrue(widget.control(action))
                self.assertEqual(called.call_args.args[0], ['playerctl', '-p', 'spotify', expected])

    def test_music_has_reloading_cover_and_icon_widgets(self):
        images = [b for k, b in self.blocks if k == 'image']
        self.assertTrue(any('widget.py music-background-image' in b and 'reload_time = 5' in b for b in images))
        self.assertTrue(any('widget.py weather-image' in b for b in images))
        self.assertTrue(any('widget.py battery-image' in b for b in images))

    def test_greeting_quotes_are_literal_not_json_encoded(self):
        self.assertIn('text = "Halo, gracie abrams"\n', self.conf)
        self.assertNotIn('\\"', self.conf)

    def test_non_square_images_use_native_lesser_side(self):
        from PIL import Image
        for kind, body in self.blocks:
            if kind != 'image': continue
            values = dict(line.strip().split(' = ', 1) for line in body.splitlines() if ' = ' in line.strip())
            if 'panel-' in values.get('path',''):
                with Image.open(values['path']) as im:
                    self.assertEqual(int(values['size']),min(im.size))
            if 'music-progress-image' in values.get('reload_cmd',''):
                self.assertEqual(values['size'],'10')

    def test_cycles_rejected_and_all_components_can_be_disabled(self):
        settings = {k:v.copy() for k,v in self.settings.items()}
        del settings['clock']['anchor']
        settings['clock']['below']='date'
        with self.assertRaisesRegex(ValueError,'circular'):
            module.render(settings,(1920,1080),self.wallpaper)
        for name in module.COMPONENTS: settings[name]['enabled']=False
        self.assertNotIn('image {',module.render(settings,(1920,1080),self.wallpaper))

    def test_scaled_render_keeps_native_panels(self):
        for dims in ((1366,768),(2560,1440)):
            conf=module.render(self.settings,dims,self.wallpaper)
            self.assertIn('music-background-',conf)
            self.assertIn('control-play-pause',conf)

    def test_lighter_regular_typography_preserves_hierarchy(self):
        labels = [dict(line.strip().split(' = ', 1) for line in body.splitlines()
                       if ' = ' in line.strip()) for kind, body in self.blocks if kind == 'label']
        clock = next(v for v in labels if 'date +%H:%M' in v['text'])
        self.assertEqual(clock['font_family'], 'Fira Sans')
        self.assertEqual(clock['font_size'], '77')
        expected = {'music-source': 11, 'music': 17, 'music-artist': 14,
                    'weather-temp': 28, 'weather-condition': 14, 'location': 14,
                    'battery': 28, 'battery-status': 13}
        for widget, size in expected.items():
            with self.subTest(widget=widget):
                label = next(v for v in labels if v['text'].endswith('widget.py ' + widget))
                self.assertEqual(label['font_size'], str(size))
                self.assertEqual(label['font_family'], 'Fira Sans')

    def test_reference_text_hierarchy_and_brightness(self):
        field = next(b for k,b in self.blocks if k == 'input-field')
        self.assertIn('outline_thickness = 0', field)
        self.assertIn('inner_color = rgba(00000000)', field)
        self.assertIn('placeholder_text = \n', field)
        self.assertIn('dots_center = true', field)
        for state in ('check', 'fail', 'capslock', 'numlock', 'bothlock'):
            self.assertIn(state + '_color = rgba(00000000)', field)
        self.assertIn('swap_font_color = false', field)
        background = next(b for k,b in self.blocks if k == 'background')
        self.assertIn('brightness = 1.0', background)
        self.assertIn('contrast = 1.0', background)
        self.assertIn('font_size = 17', next(b for k,b in self.blocks if k == 'label' and 'widget.py music\n' in b))

    def test_measured_reference_foreground_geometry(self):
        clock = next(b for k,b in self.blocks if k == 'label' and 'date +%H:%M' in b)
        self.assertIn('position = 0, 408', clock)
        for token in ('date +"%A', 'Halo,'):
            body = next(b for k,b in self.blocks if k == 'label' and token in b)
            self.assertIn('font_family = Source Code Pro', body)
            self.assertIn('font_size = 20', body)
        title = next(b for k,b in self.blocks if k == 'label' and 'widget.py music\n' in b)
        self.assertIn('position = 1397, 113', title)
        field = next(b for k,b in self.blocks if k == 'input-field')
        self.assertIn('size = 366, 64', field)
        self.assertNotIn('font_size =', field)
        self.assertIn('outer_color = rgba(00000000)', field)
        self.assertEqual(sum('onclick =' in b for k,b in self.blocks), 3)

    def test_wallpaper_blurred_and_dimmed(self):
        background = next(b for k, b in self.blocks if k == 'background')
        self.assertIn('reference-wallpaper.png', background)
        self.assertIn('blur_passes = 0', background)
        self.assertIn('brightness = 1.0', background)


if __name__ == '__main__':
    unittest.main()
