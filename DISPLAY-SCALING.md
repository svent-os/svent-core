# Automatic display scaling

BSPWM calculates bar dimensions once when its session starts. The sizing process exits after launching Polybar. It does not poll the screen or restart the bar when the VM window changes size. Polybar retains its native screen-change behavior, but the selected fonts, height and reserved window padding stay fixed until the next session startup. XFCE keeps its existing display watcher.

Polybar restarts release their launcher lock before the bar process starts. Window padding is calculated from the configured bar height and vertical offset; BSPWM's existing window gap provides the separation below the bar. Polybar struts are disabled to avoid reserving the same area twice. The generated configuration targets the primary output. All modules and separators stay visible at every scale. The original user configuration remains intact.

SventOS XFCE and BSPWM use a shared X11 display service. It chooses the active primary output, or the first active output if no primary is configured. Scaling is based on that output's resolution relative to 1920x1080, rounded to 25 percent increments and limited to 100–250 percent. Portrait modes are normalized before comparison. Ultrawide displays use the smaller dimension ratio, so extra horizontal space does not enlarge the interface excessively.

| Primary resolution | Automatic scale |
| --- | --- |
| 1280x720 | 100% |
| 1920x1080 | 100% |
| 2560x1440 | 125% |
| 3440x1440 | 125% |
| 3840x2160 | 200% |

This is a resolution-based desktop policy, not a measurement of physical display density. Virtual displays often report unreliable physical dimensions. A single shared scale follows the primary monitor; mixed-DPI monitors do not receive independent scales in these X11 sessions.

XFCE prepares its settings before session startup. The watcher updates logical DPI, panel height, panel icons, desktop icons and cursor size. BSPWM adjusts only Polybar fonts, dimensions, internal spacing and the top padding reserved for the bar. It does not modify application DPI, terminal fonts or normal window gaps. Generated bar files live in the runtime directory; the original configuration stays intact. Application support for live DPI updates varies; an application that caches DPI may need to be reopened.

The XFCE watcher checks display geometry every three seconds, applies changes only as needed, and stops after repeated display failures. XFCE settings are rechecked to account for panel startup. Only one XFCE watcher runs per X display. BSPWM sizing has no watcher or timer. Neither mode alters resolution, stretches the framebuffer, enables the compositor or starts an NTP or display-manager service.

Original XFCE XML files are preserved once in `~/.local/state/svent-display/before-auto-scaling/`. User Polybar files are never rewritten. For BSPWM, the recorded scale describes the bar rather than the applications. Diagnostics are in `$XDG_RUNTIME_DIR/svent-display-*/state.json` and `watch.log`.

To leave scaling under manual desktop control, create `~/.config/svent/display.json` containing:

```json
{"mode": "manual"}
```

To keep automatic monitoring with a preferred fixed scale:

```json
{"mode": "auto", "scale": 1.5}
```

Remove that file or set `{"mode":"auto"}` to use automatic resolution-based scaling again. XFCE rereads this preference while its watcher runs. BSPWM applies it at the next session startup. Existing scale values are not restored when switching to manual mode; adjust them through the desktop settings as desired.

## Runtime validation

Update the relevant packages and reboot to stop any watcher left over from an older version. Test XFCE and BSPWM separately at 1920x1080, 2560x1440 and 3840x2160. XFCE should update during the session. For BSPWM, choose the resolution before starting the session, verify bar dimensions and window separation, and check that no display watcher remains running afterward. Sizes should stay fixed during that session; start another session to recalculate them. Test the manual preference and confirm that application sizes remain unchanged in BSPWM.
