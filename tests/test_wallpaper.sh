#!/bin/sh
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
echo xrandr >> "$work/geometry-log"
echo "LANDSCAPEMON connected 2560x1440+0+0"
echo "PORTRAITMON connected 1080x1920+2560+0"
EOF
chmod +x "$stub"/*

export PATH="$stub:$PATH"
export HOME="$work/home"; export XDG_CONFIG_HOME="$work/home/.config"
export SVENT_WALLPAPER_CATALOG="$work/catalog.json"
mkdir -p "$XDG_CONFIG_HOME"

run() {
  BG_DIR_TEST="$bg" sh -c '
    sed "s#^BG_DIR=.*#BG_DIR=\"$BG_DIR_TEST\"#" "$0" > "$1/sel"
    sh "$1/sel" "$2" "${3:-}"
  ' "$sel" "$work" "$@"
}

check() { if eval "$2"; then echo "PASS: $1"; else echo "FAIL: $1"; fails=$((fails+1)); fi; }

out=$(run --list)
check "list shows grid-dark" 'echo "$out" | grep -q grid-dark'
check "list shows orbit-dark" 'echo "$out" | grep -q orbit-dark'

: > "$log"
run --set grid-dark >/dev/null
fehline=$(cat "$log")
check "feh called once for all monitors" '[ "$(wc -l < "$log")" -eq 1 ]'
check "monitor geometry queried once" '[ "$(wc -l < "$work/geometry-log")" -eq 1 ]'
check "landscape master used" 'echo "$fehline" | grep -q "landscape/svent-grid-dark.png"'
check "portrait master used for tall monitor" 'echo "$fehline" | grep -q "portrait/svent-grid-dark.png"'

printf '%s\n' '{"wallpapers":[{"id":"grid-dark"},{"id":"orbit-dark"}]}' > "$SVENT_WALLPAPER_CATALOG"
out=$(run --list)
check "catalog excludes unlisted aliases" '! echo "$out" | grep -q grid-light'

check "choice persisted" 'grep -q grid-dark "$XDG_CONFIG_HOME/svent/wallpaper.choice"'

custom="$work/custom.png"; : > "$custom"
: > "$log"
run --file "$custom" >/dev/null
check "override uses custom file" 'grep -q "custom.png" "$log"'

: > "$log"
run --set grid-light >/dev/null
check "built-in selection clears override" '[ ! -e "$XDG_CONFIG_HOME/svent/wallpaper.override" ]'
check "built-in selection applies after override" 'grep -q "svent-grid-light.png" "$log"'
if run --set missing-design >/dev/null 2>&1; then
  fails=$((fails+1))
else
  check "invalid selection preserves choice" 'grep -q grid-light "$XDG_CONFIG_HOME/svent/wallpaper.choice"'
fi

if run --file "$work/nope.png" >/dev/null 2>&1; then
  echo "FAIL: missing override accepted"; fails=$((fails+1))
else
  echo "PASS: missing override rejected"
fi

[ $fails -eq 0 ] && echo "all wallpaper tests passed" || echo "$fails failure(s)"
exit $fails
