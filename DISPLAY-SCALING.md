# Automatic display scaling

Polybar restarts release their launcher lock before the bar process starts. Window padding is calculated from the configured bar height, vertical offset and scaled gap; Polybar struts are disabled to avoid reserving the same area twice. The generated configuration targets the primary output. Below a logical width of 1100 pixels, the bar keeps the date, network, workspaces and power control while reducing secondary modules. The original user configuration remains intact.

SventOS XFCE and BSPWM use a shared X11 display service. It chooses the active primary output, or the first active output if no primary is configured. Scaling is based on that output's resolution relative to 1920x1080, rounded to 25 percent increments and limited to 100–250 percent. Portrait modes are normalized before comparison. Ultrawide displays use the smaller dimension ratio, so extra horizontal space does not enlarge the interface excessively.

| Primary resolution | Automatic scale |
| --- | --- |
| 1280x720 | 100% |
| 1920x1080 | 100% |
| 2560x1440 | 125% |
| 3440x1440 | 125% |
| 3840x2160 | 200% |

This is a resolution-based desktop policy, not a measurement of physical display density. Virtual displays often report unreliable physical dimensions. A single shared scale follows the primary monitor; mixed-DPI monitors do not receive independent scales in these X11 sessions.

XFCE prepares its settings before session startup. The watcher updates logical DPI, panel height, panel icons, desktop icons and cursor size. BSPWM uses X resources and an owned xsettingsd process for GTK/Qt DPI. Polybar fonts and dimensions are generated from the original configuration into the runtime directory, and window gaps and top padding follow the same scale. Kitty and Rofi use logical DPI instead of multiplied font sizes. Application support for live DPI updates varies; an application that caches DPI may need to be reopened.

The watcher checks display geometry every three seconds, applies changes only as needed, and stops after repeated display failures. XFCE settings are rechecked to account for panel startup. Only one watcher runs per X display. It does not alter resolution, stretch the framebuffer, enable the compositor or start an NTP or display-manager service.

Original XFCE XML files are preserved once in `~/.local/state/svent-display/before-auto-scaling/`. User Polybar files are never rewritten. Diagnostics are in `$XDG_RUNTIME_DIR/svent-display-*/state.json` and `watch.log`.

To leave scaling under manual desktop control, create `~/.config/svent/display.json` containing:

```json
{"mode": "manual"}
```

To keep automatic monitoring with a preferred fixed scale:

```json
{"mode": "auto", "scale": 1.5}
```

Remove that file or set `{"mode":"auto"}` to use automatic resolution-based scaling again. This preference is reread while the watcher runs. Existing scale values are not restored when switching to manual mode; adjust them through the desktop settings as desired.

## Runtime validation

Update all three packages, then log out and back in. Test XFCE and BSPWM separately at 1920x1080, 2560x1440 and 3840x2160. Resize the VM while logged in; the bar and UI should update within a few seconds. Return to 1920x1080 and check that sizes return to baseline rather than accumulating. Test primary-output changes and the manual preference. Confirm that Calamares, Firefox, terminals and menus are legible and that startup remains fast.
