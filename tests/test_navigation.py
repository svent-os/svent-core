import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import time
import unittest


@unittest.skipUnless(os.name == 'posix' and shutil.which('zsh'), 'Requires Zsh and a POSIX terminal')
class NavigationTests(unittest.TestCase):
    def test_ctrl_arrows_move_without_inserting_characters(self):
        import fcntl
        import termios
        def controlling_terminal():
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        source = Path(__file__).resolve().parents[1] / 'data/zsh/history.zsh'
        for keymap in ('emacs', 'viins'):
            for left, right in ((b'\x1b[1;5D', b'\x1b[1;5C'), (b'\x1b[5D', b'\x1b[5C')):
                for sequence, cursor in ((left, 6), (left + right, 10)):
                    with self.subTest(keymap=keymap, sequence=sequence):
                        master, slave = os.openpty()
                        process = subprocess.Popen(['zsh', '-f', '-i'], stdin=slave, stdout=slave, stderr=slave,
                                                   start_new_session=True, preexec_fn=controlling_terminal,
                                                   env={**os.environ, 'TERM': 'xterm-256color'})
                        os.close(slave)
                        try:
                            mode = '-e' if keymap == 'emacs' else '-v'
                            setup = f"bindkey {mode}; source {shlex.quote(str(source))}; svent_capture() {{ print -r -- \"SVENT_RESULT:$BUFFER:$CURSOR\"; BUFFER=; }}; zle -N svent_capture; bindkey -M {keymap} '^G' svent_capture; PS1='SVENT_NAV_READY> '; RPS1=''\n"
                            os.write(master, setup.encode())
                            output = self.read_until(master, lambda data: data.endswith(b'SVENT_NAV_READY> '))
                            self.assertTrue(output.endswith(b'SVENT_NAV_READY> '), output)
                            os.write(master, b'alpha beta' + sequence + b'\x07')
                            expected = f'SVENT_RESULT:alpha beta:{cursor}'.encode()
                            result = self.read_until(master, lambda data: expected in data)
                            self.assertIn(expected, result)
                        finally:
                            process.terminate()
                            try:
                                process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                            os.close(master)

    def read_until(self, descriptor, complete):
        data = b''
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            ready, _, _ = select.select([descriptor], [], [], 0.1)
            if ready:
                data += os.read(descriptor, 65536)
                if complete(data):
                    break
        return data


if __name__ == '__main__':
    unittest.main()
