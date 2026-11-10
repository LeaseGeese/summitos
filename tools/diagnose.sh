#!/bin/bash
# Summit OS diagnostics: a short, readable report on graphics, compositor, CPU, memory, disk and appearance.
#   curl -fsSL https://raw.githubusercontent.com/LeaseGeese/summitos/main/tools/diagnose.sh | bash
# Prints a summary and saves the full report to ~/Desktop/summit-report.txt. Changes nothing.
OUT="$HOME/Desktop/summit-report.txt"; mkdir -p "$HOME/Desktop"
LOGX=$(ls -t "$HOME/.local/share/xorg/Xorg.0.log" /var/log/Xorg.0.log 2>/dev/null | head -1)
{
echo "=== Summit report $(date '+%F %T')"
grep PRETTY_NAME /etc/os-release | cut -d'"' -f2
echo "updates: $(python3 -c 'import json;c=json.load(open("/etc/summit/update.json"));print(c.get("repo") or "not set up", "live" if c.get("live") else "")' 2>/dev/null || echo 'updater not installed')"
echo "model: $(cat /sys/class/dmi/id/product_name 2>/dev/null)  ram: $(free -g | awk '/Mem:/{print $2+1}') GB  cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
echo
echo "--- graphics"
lspci -nnk 2>/dev/null | grep -A3 -iE 'vga|display' | grep -E 'VGA|Display|driver in use' | sed 's/^\s*//'
[ -n "$LOGX" ] && grep -E 'LoadModule: "(intel|modesetting)"|\((II|EE)\) (intel|modeset)\([0-9]\): (Using|SNA|glamor|Integrated)|AccelMethod|glamor initialized|Failed' "$LOGX" | sed 's/^\[ *[0-9.]*\] //' | head -8
echo "screen: $(xrandr 2>/dev/null | grep -m1 '\*' | xargs)"
echo
echo "--- compositor"
pgrep -a picom | cut -c1-120 || echo "picom NOT running"
[ -f "$HOME/.config/summit/no-gpu-blur" ] && echo "mode: software (no GPU blur)" || echo "mode: GPU"
grep -E "GPU mode|software mode|blank screen|crashed|didn't start" "$HOME/.cache/summit-picom.log" 2>/dev/null | tail -n 3
[ -f "$HOME/.config/summit/no-picom12" ] && echo "picom 12 disabled on this Mac (fell back to picom 10)"
echo "tuning: cpu floor $(cat /sys/devices/system/cpu/intel_pstate/min_perf_pct 2>/dev/null)%  gpu min $(cat /sys/class/drm/card*/gt_min_freq_mhz 2>/dev/null | head -1) MHz of $(cat /sys/class/drm/card*/gt_RP0_freq_mhz 2>/dev/null | head -1)  boot: $(grep -o 'preempt=[a-z]*' /proc/cmdline || echo 'preempt default')"
echo
echo "--- load"
uptime | sed 's/.*load/load/'
echo "cpu MHz: $(awk -F: '/MHz/{s+=$2;n++} END{if(n) printf "%d", s/n}' /proc/cpuinfo)  governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)  temp: $(( $(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1) / 1000 ))C"
ps -eo pcpu,rss,comm --sort=-pcpu | head -9 | awk 'NR==1{print "  %CPU  MB  PROCESS"; next}{printf "  %4s %4d  %s\n", $1, $2/1024, $3}'
free -m | awk '/Mem:/{print "memory used: "$3" MB of "$2" MB"} /Swap:/{print "swap used: "$3" MB"}'
echo
echo "--- disk"
R=$(findmnt -no SOURCE /); D=$(lsblk -no PKNAME "$R" | head -1)
echo "startup disk: /dev/$D $(lsblk -dno MODEL,TRAN,SIZE /dev/$D | xargs)  rotational=$(cat /sys/block/$D/queue/rotational)  scheduler=$(grep -o '\[.*\]' /sys/block/$D/queue/scheduler)"
echo
echo "--- appearance"
cat "$HOME/.config/summit/appearance.json" 2>/dev/null | tr -d '\n ' ; echo
echo "theme: $(xfconf-query -c xsettings -p /Net/ThemeName)  icons: $(xfconf-query -c xsettings -p /Net/IconThemeName)"
ACC=$(python3 -c 'import json;print(json.load(open("'"$HOME"'/.config/summit/appearance.json")).get("accent","blue"))' 2>/dev/null || echo blue)
S=$(date +%s%N); ERR=$(SUMMIT_APPEARANCE_LOCAL=1 timeout 120 summit-appearance set accent="$ACC" 2>&1 | tail -3); E=$(date +%s%N)
echo "re-applying accent '$ACC' took $(( (E - S) / 1000000 )) ms ${ERR:+error: $ERR}"
echo
echo "--- recent errors"
journalctl -b -p err --no-pager -q 2>/dev/null | tail -n 6 | cut -c17-160
journalctl --user -b -p warning --no-pager -q 2>/dev/null | grep -iE 'summit|picom|plank|xfce|python' | tail -n 6 | cut -c17-160
tail -n 8 "$HOME/.xsession-errors" 2>/dev/null | grep -viE 'dbind|a11y' | cut -c1-160
} > "$OUT" 2>&1
cat "$OUT"
echo
echo "Saved to Desktop/summit-report.txt"
