from importlib.machinery import SourceFileLoader
from pathlib import Path
import shutil
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
configuration = SourceFileLoader('svent_shell_configuration', str(ROOT / 'bin/configure-shell')).load_module()


class ShellConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / ('shell-test-' + uuid.uuid4().hex)
        (self.root / 'etc/zsh').mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_preserves_configuration_and_creates_backup_only_once(self):
        path = self.root / 'etc/zsh/zshrc'
        original = 'export PERSONAL_SETTING=yes\n\n'
        path.write_text(original)
        configuration.configure(self.root)
        configuration.configure(self.root)
        self.assertEqual(path.read_text(), original + configuration.INTEGRATION + '\n')
        self.assertEqual((self.root / 'var/lib/svent-core/zshrc.before-navigation').read_text(), original)

    def test_refuses_existing_temporary_file_without_changing_configuration(self):
        path = self.root / 'etc/zsh/zshrc'
        path.write_text('original\n')
        path.with_name('zshrc.svent-tmp').write_text('preserve\n')
        with self.assertRaises(RuntimeError):
            configuration.configure(self.root)
        self.assertEqual(path.read_text(), 'original\n')
