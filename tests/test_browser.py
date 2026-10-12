from importlib.machinery import SourceFileLoader
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[1]
browser = SourceFileLoader('svent_browser', str(ROOT / 'bin/configure-browser')).load_module()


class BrowserTests(unittest.TestCase):
    def test_migration_preserves_unrelated_defaults_and_original_backup(self):
        home = ROOT / ('browser-test-' + uuid.uuid4().hex)
        path = home / '.config/mimeapps.list'
        path.parent.mkdir(parents=True)
        original = '[Default Applications]\napplication/pdf=viewer.desktop;\nx-scheme-handler/https=other.desktop;\n'
        path.write_text(original)
        try:
            with patch.object(browser.os, 'chown', create=True):
                browser.configure(home, 1000, 1000)
                browser.configure(home, 1000, 1000)
            self.assertIn('application/pdf = viewer.desktop;', path.read_text())
            self.assertIn('x-scheme-handler/https = firefox-esr.desktop;', path.read_text())
            self.assertEqual((home / '.local/state/svent-core/browser-before-0.4.8/.config/mimeapps.list').read_text(), original)
            self.assertIn('WebBrowser = custom-WebBrowser', (home / '.config/xfce4/helpers.rc').read_text())
            self.assertIn('X-XFCE-Commands=firefox-esr;', (home / '.local/share/xfce4/helpers/custom-WebBrowser.desktop').read_text())
        finally:
            shutil.rmtree(home)
