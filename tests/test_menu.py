import importlib.machinery
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("menu_generator", str(ROOT / "bin/gen-menu"))
spec = importlib.util.spec_from_loader(loader.name, loader)
menu = importlib.util.module_from_spec(spec)
loader.exec_module(menu)

class MenuGeneration(unittest.TestCase):
    def test_preserves_unrelated_launchers_and_removes_stale_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            apps = root / "usr/share/applications"
            apps.mkdir(parents=True)
            unrelated = apps / "svent-xfce-backgrounds.desktop"
            unrelated.write_text("[Desktop Entry]\nExec=svent-xfce-wallpaper\n")
            old = apps / "svent-old.desktop"
            old.write_text("[Desktop Entry]\nExec=svent-run old\n")
            data = {"groups": {"web": {"name": "Web & Apps"}}, "tools": [
                {"name": "test", "description": "First\nSecond", "executables": ["test"], "group": "web"}]}
            menu.generate(root, data)
            self.assertTrue(unrelated.is_file())
            self.assertFalse(old.exists())
            generated = apps / "svent-test.desktop"
            self.assertIn("First\\nSecond", generated.read_text())
            xml = root / "etc/xdg/menus/applications-merged/svent-tools.menu"
            self.assertEqual(ET.parse(xml).getroot().find("Menu/Name").text, "SventOS")
            stamp = generated.stat().st_mtime_ns
            menu.generate(root, data)
            self.assertEqual(generated.stat().st_mtime_ns, stamp)
            menu.generate(root, clean=True)
            self.assertTrue(unrelated.is_file())
            self.assertFalse(generated.exists())

    def test_graphical_launcher_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            apps = root / "usr/share/applications"
            apps.mkdir(parents=True)
            graphical = apps / "sv-burpsuite.desktop"
            graphical.write_text("[Desktop Entry]\nName=Burp Suite (Community)\nTerminal=false\n")
            old = apps / "svent-burpsuite.desktop"
            old.write_text("[Desktop Entry]\nExec=svent-run burpsuite\nTerminal=true\n")
            data = {"groups": {"web": {"name": "Web"}}, "tools": [
                {"name": "burpsuite", "description": "Burp Suite", "executables": ["burpsuite"],
                 "group": "web", "desktop_file": "sv-burpsuite.desktop"}]}
            menu.generate(root, data)
            self.assertTrue(graphical.is_file())
            self.assertFalse(old.exists())
            self.assertEqual(len(list(apps.glob("*burpsuite.desktop"))), 1)
            menu.generate(root, clean=True)
            self.assertTrue(graphical.is_file())

if __name__ == "__main__":
    unittest.main()
