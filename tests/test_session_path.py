from pathlib import Path
import os
import subprocess
import unittest


@unittest.skipUnless(os.name == 'posix', 'Requires a native POSIX shell')
class SessionPathTests(unittest.TestCase):
    def test_command_directories_are_added_without_duplicates(self):
        source = Path(__file__).resolve().parents[1] / 'data/session/svent-path.sh'
        result = subprocess.run(['/bin/sh', '-c', '. "$1"; . "$1"; printf "%s" "$PATH"',
                                 'test', str(source)], env={'PATH': '/usr/bin:/bin:/usr/sbin'},
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '/usr/bin:/bin:/usr/sbin:/usr/local/sbin:/sbin')
