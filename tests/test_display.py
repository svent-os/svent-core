from pathlib import Path
import shutil
import unittest
import uuid
from svent.display import choose_scale, monitors, polybar_config, settings, xfce_values, xml_values
import xml.etree.ElementTree as ET


class DisplayTests(unittest.TestCase):
    def test_supported_resolutions_and_portrait(self):
        for width, height, expected in [(1280, 720, 1), (1920, 1080, 1), (2560, 1440, 1.25),
                                        (3840, 2160, 2), (7680, 4320, 2.5), (2160, 3840, 2),
                                        (3440, 1440, 1.25), (3840, 1080, 1)]:
            with self.subTest(width=width, height=height):
                self.assertEqual(choose_scale([{'width': width, 'height': height, 'primary': True}]), expected)

    def test_primary_output_does_not_sum_desktop_width(self):
        text = 'HDMI-1 connected 3840x2160+1920+0\nDP-1 connected primary 1920x1080+0+0\nDP-2 connected (normal left inverted right)\n'
        outputs = monitors(text)
        self.assertEqual(len(outputs), 2)
        self.assertEqual(choose_scale(outputs), 1)
        self.assertEqual(choose_scale([]), 1)

    def test_polybar_scaling_preserves_modules_and_is_not_cumulative(self):
        original = '[global/wm]\ninclude-file = modules.ini\n[bar/example]\nheight = 34px\nfont-0 = JetBrains Mono:pixelsize=11;3\nmodules-left = date network\n[settings]\nscreenchange-reload = true\n'
        output = polybar_config(original, 2, Path('/home/example'))
        self.assertIn('[bar/example]\ndpi = 96', output)
        self.assertIn('height = 68px', output)
        self.assertIn('pixelsize=22;6', output)
        self.assertIn('modules-left = date network', output)
        self.assertIn('/home/example/.config/polybar/modules.ini', output)
        self.assertEqual(polybar_config(original, 1, Path('/home/example')).count('height = 34px'), 1)

    def test_configuration_preserves_theme_and_original_backup(self):
        home = Path(__file__).resolve().parents[1] / ('display-test-' + uuid.uuid4().hex)
        path = home / '.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml'
        path.parent.mkdir(parents=True)
        original = '<channel name="xsettings" version="1.0"><property name="Net" type="empty"><property name="ThemeName" type="string" value="Personal"/></property></channel>'
        path.write_text(original)
        try:
            xml_values(home, 'xsettings', xfce_values(2)['xsettings'])
            xml_values(home, 'xsettings', xfce_values(1)['xsettings'])
            tree = ET.parse(path)
            self.assertEqual(tree.find(".//property[@name='ThemeName']").get('value'), 'Personal')
            self.assertEqual(tree.find(".//property[@name='DPI']").get('value'), '96')
            self.assertEqual((home / '.local/state/svent-display/before-auto-scaling/xsettings.xml').read_text(), original)
        finally:
            shutil.rmtree(home)

    def test_manual_mode_and_invalid_override(self):
        home = Path(__file__).resolve().parents[1] / ('display-test-' + uuid.uuid4().hex)
        path = home / '.config/svent/display.json'
        path.parent.mkdir(parents=True)
        try:
            path.write_text('{"mode":"manual"}')
            self.assertEqual(settings(home)['mode'], 'manual')
            path.write_text('{"scale":10}')
            with self.assertRaises(ValueError):
                settings(home)
        finally:
            shutil.rmtree(home)
