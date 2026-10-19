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

    def test_control_badges_and_compact_fonts(self):
        self.assertEqual(self.conf.count('size = 35, 27'), 3)
        self.assertIn('font_size = 12', self.conf)
        self.assertIn('font_size = 10', self.conf)
        self.assertIn('font_size = 16', self.conf)

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
        labels = [b for k, b in self.blocks if k == 'label']
        for action in ('previous', 'play-pause', 'next'):
            self.assertTrue(any('onclick = python3 ' in b and 'control-' + action in b for b in labels))
        self.assertIn('font_family = JetBrains Mono', self.conf)

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
        self.assertTrue(any('widget.py cover' in b and 'reload_time = 10' in b for b in images))
        labels = [b for k, b in self.blocks if k == 'label']
        self.assertTrue(any('widget.py weather-icon' in b for b in labels))
        self.assertTrue(any('widget.py battery-icon' in b for b in labels))

    def test_wallpaper_blurred_and_dimmed(self):
        background = next(b for k, b in self.blocks if k == 'background')
        self.assertRegex(background, r'blur_passes = [2-9]')
        self.assertRegex(background, r'brightness = 0\.[4-7]')


if __name__ == '__main__':
    unittest.main()
