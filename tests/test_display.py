from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import uuid
from svent.display import apply_display, bar_layout, choose_scale, initialize_bspwm, main, monitors, polybar_config, settings, watch, xfce_values, xml_values
import xml.etree.ElementTree as ET


class DisplayTests(unittest.TestCase):
    def test_bspwm_initialization_detects_and_applies_only_once(self):
        outputs = [{'name': 'Virtual1', 'primary': True, 'width': 3840, 'height': 2160}]
        with patch('svent.display.settings', return_value={'mode': 'auto'}), patch('svent.display.detect', return_value=outputs) as detect, patch('svent.display.apply_bspwm') as bar, patch('svent.display.state_write') as record:
            initialize_bspwm(Path('/home/example'), Path('/run/example'))
            detect.assert_called_once()
            bar.assert_called_once_with(Path('/home/example'), Path('/run/example'), 2, outputs)
            self.assertEqual(record.call_args.args[1]['sizing'], 'session-start')

    def test_bspwm_watch_action_returns_without_polling(self):
        with patch('svent.display.runtime'), patch('svent.display.initialize_bspwm') as initialize, patch('svent.display.time.sleep') as sleep:
            watch('bspwm')
            initialize.assert_called_once()
            sleep.assert_not_called()

    def test_bspwm_start_does_not_spawn_a_background_watcher(self):
        with patch.dict('os.environ', {'DISPLAY': ':77'}), patch('sys.argv', ['display-scale', 'start', 'bspwm']), patch('svent.display.runtime'), patch('svent.display.initialize_bspwm') as initialize, patch('svent.display.subprocess.Popen') as process:
            main()
            initialize.assert_called_once()
            process.assert_not_called()

    def test_bspwm_adjustment_does_not_change_application_dpi(self):
        with patch('svent.display.run') as command, patch('svent.display.apply_bspwm') as bar, patch('svent.display.apply_xfce') as xfce:
            apply_display(Path('/home/example'), Path('/run/example'), 'bspwm', 2, [])
            bar.assert_called_once()
            command.assert_not_called()
            xfce.assert_not_called()

    def test_bar_window_spacing_follows_actual_dimensions(self):
        config = '[bar/example]\nheight = 40px\noffset-y = 10px\n'
        layout = bar_layout(config, 2)
        self.assertEqual(layout['height'], 80)
        self.assertEqual(layout['offset'], 20)
        self.assertEqual(layout['top_padding'], 100)

    def test_bar_reserves_its_bottom_edge_without_adding_another_gap(self):
        config = '[bar/example]\nheight = 34px\noffset-y = 8px\n'
        for scale in (1, 1.25, 2):
            with self.subTest(scale=scale):
                layout = bar_layout(config, scale)
                self.assertEqual(layout['top_padding'], layout['height'] + layout['offset'])

    def test_scale_preserves_all_modules_and_separators(self):
        config = '[bar/example]\nmodules-left = date divider network\nmodules-right = target divider power\nenable-struts = true\n'
        large = polybar_config(config, 2, Path('/home/example'))
        normal = polybar_config(config, 1, Path('/home/example'))
        self.assertIn('modules-left = date divider network', large)
        self.assertIn('modules-right = target divider power', large)
        self.assertIn('modules-right = target divider power', normal)
        self.assertIn('enable-struts = false', normal)
        self.assertNotIn('enable-struts = true', normal)

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
