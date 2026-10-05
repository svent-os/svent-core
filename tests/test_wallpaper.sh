#!/bin/sh
# Test svent-wallpaper selection logic with stubbed desktop commands.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
sel="$here/../bin/svent-wallpaper"
fails=0

sh -n "$sel" || { echo "FAIL: syntax error"; exit 1; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
bg="$work/bg"; stub="$work/stub"; log="$work/log"
mkdir -p "$bg/landscape" "$bg/portrait" "$stub"
for c in grid-dark grid-light orbit-dark; do
  : > "$bg/landscape/svent-$c.png"
  : > "$bg/portrait/svent-$c.png"
done

# Stub binaries that record their arguments
cat > "$stub/feh" <<EOF
#!/bin/sh
echo "feh \$*" >> "$log"
EOF
cat > "$stub/bspc" <<EOF
#!/bin/sh
case "\$*" in
  "query -T -m") exit 0 ;;
  "query -M --names") echo "LANDSCAPEMON"; echo "PORTRAITMON" ;;
esac
EOF
cat > "$stub/xrandr" <<EOF
#!/bin/sh
echo "LANDSCAPEMON connected 2560x1440+0+0"
echo "PORTRAITMON connected 1080x1920+2560+0"
EOF
chmod +x "$stub"/*

export PATH="$stub:$PATH"
export HOME="$work/home"; export XDG_CONFIG_HOME="$work/home/.config"
mkdir -p "$XDG_CONFIG_HOME"

# Point the script at our test background dir and force bspwm path
run() {
  BG_DIR_TEST="$bg" sh -c '
    sed "s#^BG_DIR=.*#BG_DIR=\"$BG_DIR_TEST\"#" "$0" > "$1/sel"
    sh "$1/sel" "$2" ${3:-}
  ' "$sel" "$work" "$@"
}

check() { if eval "$2"; then echo "PASS: $1"; else echo "FAIL: $1"; fails=$((fails+1)); fi; }

# --list should show the three installed designs
out=$(run --list)
check "list shows grid-dark" 'echo "$out" | grep -q grid-dark'
check "list shows orbit-dark" 'echo "$out" | grep -q orbit-dark'

# bspwm apply: landscape monitor gets landscape master, portrait gets portrait
: > "$log"
run --set grid-dark >/dev/null
fehline=$(cat "$log")
check "feh called bg-fill twice" '[ "$(grep -c bg-fill "$log")" -ge 1 ]'
check "landscape master used" 'echo "$fehline" | grep -q "landscape/svent-grid-dark.png"'
check "portrait master used for tall monitor" 'echo "$fehline" | grep -q "portrait/svent-grid-dark.png"'

# choice persists
check "choice persisted" 'grep -q grid-dark "$XDG_CONFIG_HOME/svent/wallpaper.choice"'

# override wins and uses the custom file
custom="$work/custom.png"; : > "$custom"
: > "$log"
run --file "$custom" >/dev/null
check "override uses custom file" 'grep -q "custom.png" "$log"'

# missing custom file is rejected (non-zero)
if run --file "$work/nope.png" >/dev/null 2>&1; then
  echo "FAIL: missing override accepted"; fails=$((fails+1))
else
  echo "PASS: missing override rejected"
fi

[ $fails -eq 0 ] && echo "all wallpaper tests passed" || echo "$fails failure(s)"
exit $fails
