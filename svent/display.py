import argparse
import configparser
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def monitors(text):
    outputs = []
    for line in text.splitlines():
        match = re.match(r'^(\S+) connected (primary )?(\d+)x(\d+)[+-]\d+[+-]\d+', line)
        if match:
            outputs.append({'name': match[1], 'primary': bool(match[2]),
                            'width': int(match[3]), 'height': int(match[4])})
    return outputs


def choose_scale(outputs):
    if not outputs:
        return 1.0
    output = next((item for item in outputs if item['primary']), outputs[0])
    long, short = sorted((output['width'], output['height']), reverse=True)
    ratio = min(long / 1920, short / 1080)
    return min(2.5, max(1.0, math.floor(ratio * 4 + 0.5) / 4))


def settings(home):
    path = home / '.config/svent/display.json'
    if not path.is_file():
        return {'mode': 'auto'}
    result = json.loads(path.read_text())
    if result.get('mode', 'auto') not in ('auto', 'manual'):
        raise ValueError('Display mode must be auto or manual')
    if 'scale' in result:
        value = float(result['scale'])
        if not math.isfinite(value) or not 1 <= value <= 2.5:
            raise ValueError('Display scale must be between 1 and 2.5')
    return result


def run(args, text=None):
    return subprocess.run(args, input=text, text=True, capture_output=True, timeout=2)


def detect():
    result = run(['xrandr', '--current'])
    if result.returncode:
        raise RuntimeError('The X display is unavailable')
    return monitors(result.stdout)


def runtime():
    folder = Path(os.environ.get('XDG_RUNTIME_DIR', str(Path.home() / '.cache')))
    suffix = hashlib.sha256(os.environ.get('DISPLAY', '').encode()).hexdigest()[:12]
    folder = folder / ('svent-display-' + suffix)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def state_write(folder, record):
    temporary = folder / 'state.tmp'
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    temporary.replace(folder / 'state.json')


def xml_values(home, channel, properties):
    path = home / '.config/xfce4/xfconf/xfce-perchannel-xml' / (channel + '.xml')
    if path.is_symlink() or not path.parent.resolve().is_relative_to(home.resolve()):
        raise RuntimeError('Unsafe display configuration path')
    backup = home / '.local/state/svent-display/before-auto-scaling' / (channel + '.xml')
    if path.exists() and not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element('channel', name=channel, version='1.0'))
    for key, kind, value in properties:
        parent = tree.getroot()
        parts = key.strip('/').split('/')
        for name in parts[:-1]:
            child = parent.find("property[@name='" + name + "']")
            if child is None:
                child = ET.SubElement(parent, 'property', name=name, type='empty')
            parent = child
        child = parent.find("property[@name='" + parts[-1] + "']")
        if child is None:
            child = ET.SubElement(parent, 'property', name=parts[-1])
        child.set('type', kind)
        child.set('value', str(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding='utf-8', xml_declaration=True)


def xfce_values(scale):
    return {
        'xsettings': [('/Xft/DPI', 'int', round(96 * scale)),
                      ('/Gdk/WindowScalingFactor', 'int', 1),
                      ('/Gtk/CursorThemeSize', 'int', round(24 * scale))],
        'xfce4-panel': [('/panels/panel-1/size', 'uint', round(36 * scale)),
                        ('/panels/panel-1/icon-size', 'uint', round(24 * scale))],
        'xfce4-desktop': [('/desktop-icons/icon-size', 'uint', round(40 * scale))]}


def apply_xfce(scale):
    import gi
    gi.require_version('Xfconf', '0')
    from gi.repository import Xfconf
    if not Xfconf.init():
        raise RuntimeError('Xfconf is unavailable')
    try:
        for name, properties in xfce_values(scale).items():
            channel = Xfconf.Channel.get(name)
            for key, kind, value in properties:
                if not channel.has_property(key) or getattr(channel, 'get_' + kind)(key, value) != value:
                    getattr(channel, 'set_' + kind)(key, value)
    finally:
        Xfconf.shutdown()


def polybar_config(text, scale, home):
    pixel_keys = {'height', 'offset-y', 'radius', 'padding-left', 'padding-right'}
    lines = []
    for line in text.splitlines():
        if line.startswith('[bar/'):
            lines.extend([line, 'dpi = 96'])
            continue
        match = re.match(r'^(\s*)([\w-]+)(\s*=\s*)(\d+)(px)?$', line)
        if match and match[2] in pixel_keys:
            line = f'{match[1]}{match[2]}{match[3]}{round(int(match[4]) * scale)}{match[5] or ""}'
        if line.startswith('font-'):
            line = re.sub(r'pixelsize=(\d+)', lambda m: 'pixelsize=' + str(round(int(m[1]) * scale)), line)
            line = re.sub(r';(\d+)$', lambda m: ';' + str(round(int(m[1]) * scale)), line)
        if line.strip() == 'include-file = modules.ini':
            line = 'include-file = ' + (home / '.config/polybar/modules.ini').as_posix()
        lines.append(line)
    return '\n'.join(lines) + '\n'


def bspwm_settings(home, scale):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(home / '.config/gtk-3.0/settings.ini')
    values = {'Net/ThemeName': parser.get('Settings', 'gtk-theme-name', fallback='Greybird-dark'),
              'Net/IconThemeName': parser.get('Settings', 'gtk-icon-theme-name', fallback='Svent'),
              'Gtk/FontName': parser.get('Settings', 'gtk-font-name', fallback='Sans 10')}
    return ''.join(key + ' ' + json.dumps(value) + '\n' for key, value in values.items()) + f'Xft/DPI {round(96 * scale * 1024)}\nGtk/CursorThemeSize {round(24 * scale)}\n'


def apply_bspwm(home, folder, scale):
    source = home / '.config/polybar/config.ini'
    if source.is_file():
        contents = polybar_config(source.read_text(), scale, home)
        modules = home / '.config/polybar/modules.ini'
        if modules.is_file():
            scaled_modules = folder / 'polybar-modules.ini'
            scaled_modules.write_text(re.sub(r'(\d+)px', lambda m: str(round(int(m[1]) * scale)) + 'px', modules.read_text()))
            contents = contents.replace(modules.as_posix(), scaled_modules.as_posix())
        (folder / 'polybar.ini').write_text(contents)
    run(['bspc', 'config', 'top_padding', str(round(50 * scale))])
    run(['bspc', 'config', 'window_gap', str(round(9 * scale))])
    launch = home / '.config/polybar/launch.sh'
    if launch.is_file():
        subprocess.Popen(['bash', str(launch)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def watch(desktop):
    import fcntl
    folder = runtime()
    with (folder / 'watch.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        home = Path.home()
        previous = None
        failures = 0
        xsettings = None
        try:
            while True:
                try:
                    desktop = (folder / 'desktop').read_text().strip()
                    config = settings(home)
                    outputs = detect()
                    if config.get('mode', 'auto') == 'manual':
                        if xsettings is not None:
                            xsettings.terminate()
                            xsettings.wait(timeout=2)
                            xsettings = None
                        previous = None
                        time.sleep(3)
                        continue
                    scale = float(config.get('scale', choose_scale(outputs)))
                    signature = (desktop, scale, json.dumps(outputs, sort_keys=True))
                    if signature != previous:
                        run(['xrdb', '-merge'], f'Xft.dpi: {round(96 * scale)}\nXcursor.size: {round(24 * scale)}\n')
                        if desktop == 'xfce':
                            if xsettings is not None:
                                xsettings.terminate()
                                xsettings.wait(timeout=2)
                                xsettings = None
                            apply_xfce(scale)
                        else:
                            path = folder / 'xsettingsd.conf'
                            path.write_text(bspwm_settings(home, scale))
                            if xsettings is None or xsettings.poll() is not None:
                                xsettings = subprocess.Popen(['xsettingsd', '-c', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            else:
                                xsettings.send_signal(signal.SIGHUP)
                            apply_bspwm(home, folder, scale)
                        state_write(folder, {'desktop': desktop, 'scale': scale, 'dpi': round(96 * scale), 'outputs': outputs})
                        previous = signature
                    elif desktop == 'xfce':
                        apply_xfce(scale)
                    failures = 0
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                    print('SventOS display: ' + str(error), file=sys.stderr, flush=True)
                    failures += 1
                    if failures >= 3:
                        return
                time.sleep(3)
        finally:
            if xsettings is not None and xsettings.poll() is None:
                xsettings.terminate()
                xsettings.wait(timeout=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'start', 'watch'])
    parser.add_argument('desktop', choices=['xfce', 'bspwm'])
    args = parser.parse_args()
    if not os.environ.get('DISPLAY'):
        return
    if args.action == 'watch':
        watch(args.desktop)
        return
    folder = runtime()
    if args.action == 'prepare':
        config = settings(Path.home())
        if config.get('mode', 'auto') == 'manual':
            return
        scale = float(config.get('scale', choose_scale(detect())))
        if args.desktop == 'xfce':
            for channel, properties in xfce_values(scale).items():
                xml_values(Path.home(), channel, properties)
        run(['xrdb', '-merge'], f'Xft.dpi: {round(96 * scale)}\n')
    (folder / 'desktop').write_text(args.desktop)
    with (folder / 'watch.log').open('a') as log:
        subprocess.Popen([sys.executable, '/usr/libexec/svent/display-scale', 'watch', args.desktop], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)


if __name__ == '__main__':
    main()
