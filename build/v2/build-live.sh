#!/bin/bash
# Summit OS 2.0: builds the live image from an empty directory on Debian 13 packages.
#   sudo build/v2/build-live.sh [workdir]          (needs root, ~15 GB free, debootstrap squashfs-tools xorriso grub)
# Steps: 1 minimal Debian base  2 the packages in packages.txt  3 drivers compiled, compiler removed again
#        4 Summit's files  5 system setup  6 squashfs + bootable ISO (BIOS and UEFI)
# Behind an HTTPS proxy: export HTTPS_PROXY and BUILD_CA=/path/to/ca.crt.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; V2="$REPO/build/v2"
W="${1:-/var/tmp/summit2-build}"; R="$W/chroot"
LABEL="${SUMMIT_LABEL:-2.0 alpha 1}"; FILEVER="${LABEL// /-}"
MIRROR=https://deb.debian.org/debian
mounts() { for d in proc sys dev dev/pts; do mountpoint -q "$R/$d" || mount --bind "/$d" "$R/$d"; done; }
umounts() { for d in dev/pts dev sys proc; do umount -l "$R/$d" 2>/dev/null || true; done; }
proxy_on() { [ -n "${HTTPS_PROXY:-}" ] || return 0; printf 'Acquire::https::Proxy "%s";\n' "$HTTPS_PROXY" > "$R/etc/apt/apt.conf.d/00buildproxy"
             [ -n "${BUILD_CA:-}" ] && { cp "$BUILD_CA" "$R/tmp/build-ca.crt"; echo 'Acquire::https::CaInfo "/tmp/build-ca.crt";' >> "$R/etc/apt/apt.conf.d/00buildproxy"; }; return 0; }
proxy_off() { rm -f "$R/etc/apt/apt.conf.d/00buildproxy" "$R/tmp/build-ca.crt"; }
run() { chroot "$R" env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 DEBIAN_FRONTEND=noninteractive "$@"; }
list() { sed 's/#.*//' "$1" | tr '\n' ' '; }
step() { echo; echo "== $*"; }
mkdir -p "$W"

step "1 base"
if [ ! -d "$R/etc" ]; then
  debootstrap --arch=amd64 --variant=minbase --components=main,contrib,non-free,non-free-firmware --include=ca-certificates trixie "$R" $MIRROR/
fi
cat > "$R/etc/apt/sources.list" <<EOT
deb $MIRROR trixie main contrib non-free non-free-firmware
deb $MIRROR trixie-updates main contrib non-free non-free-firmware
deb https://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware
EOT
printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"; chmod +x "$R/usr/sbin/policy-rc.d"
printf 'APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\n' > "$R/etc/apt/apt.conf.d/99summit-minimal"
trap 'umounts; proxy_off' EXIT; mounts; proxy_on

step "2 packages"
run apt-get update -q
run apt-get -y -q -o Dpkg::Options::=--force-confold upgrade
run apt-get -y -q -o Dpkg::Options::=--force-confold install $(list "$V2/packages.txt")
run sh -c 'sed -i "s/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/" /etc/locale.gen && locale-gen >/dev/null && update-locale LANG=en_US.UTF-8'

step "3 drivers (compiled now, so no compiler ships in the image)"
KV=$(ls "$R/lib/modules" | sort -V | tail -1)
rm -rf "$R/lib/modules/$KV/updates" "$R/var/lib/dkms" "$R"/usr/src/summit-magicmouse-*   # never reuse a previous run's results
mkdir -p "$R/usr/src"; cp -a "$REPO/overlay/usr/src/." "$R/usr/src/"
run apt-get -y -q install $(list "$V2/build-only.txt")
MM=$(basename "$R"/usr/src/summit-magicmouse-*); MMV=${MM#summit-magicmouse-}
run sh -c "ls /lib/modules/$KV/updates/dkms/wl.ko* >/dev/null 2>&1 || dkms autoinstall -k $KV" || true
run sh -c "dkms add -m summit-magicmouse -v $MMV 2>/dev/null; dkms install -m summit-magicmouse -v $MMV -k $KV" || true
mkdir -p "$W/modules"; rm -f "$W/modules/"*
find "$R/lib/modules/$KV/updates/dkms" -name '*.ko*' -exec cp {} "$W/modules/" \; 2>/dev/null || true
for m in wl hid-magicmouse; do ls "$W/modules/$m".ko* >/dev/null 2>&1 || { echo "ERROR: driver $m did not build"; exit 1; }; done
run apt-get -y -q purge $(list "$V2/build-only.txt") 'linux-headers-*' 'linux-kbuild-*'
run apt-get -y -q -o APT::AutoRemove::SuggestsImportant=false autoremove --purge
rm -rf "$R/var/lib/dkms" "$R"/usr/src/summit-magicmouse-* "$R/lib/modules/$KV/updates/dkms"
mkdir -p "$R/lib/modules/$KV/updates/summit"; cp "$W/modules/"* "$R/lib/modules/$KV/updates/summit/"
run depmod "$KV"
if run sh -c 'command -v gcc || command -v make || command -v dkms' >/dev/null; then echo "ERROR: build tools are still in the image"; exit 1; fi

step "4 Summit's files"
while read -r from to; do
  [ -n "$from" ] || continue
  run mkdir -p "$(dirname "$to")"; run dpkg-divert --local --rename --divert "$to" --add "$from" >/dev/null
done < <(cat "$REPO/build/diversions.txt" "$V2/diversions.txt")
# the menu bar's parts run inside the bar itself, so they take on its translucent look: Summit's copies of
# these three definitions are the originals (moved aside above) with that one setting changed
for f in systray pulseaudio whiskermenu; do
  d="$R/usr/share/xfce4/panel/plugins/$f.desktop"
  [ -e "$d.summit-orig" ] || { echo "ERROR: menu bar part $f is missing"; exit 1; }
  grep -vi '^X-XFCE-Internal=' "$d.summit-orig" | sed 's/^\[Xfce Panel\]$/[Xfce Panel]\nX-XFCE-Internal=TRUE/' > "$d"
done
rm -f "$R/usr/local/lib/summitos/picom"
cp -a "$REPO/overlay/." "$R/"
cp -a "$V2/overlay/." "$R/"
# not part of 2.0: the 1.x installer (2.0's installer comes in a later phase), Ubuntu's live system settings,
# compiler sources, and Summit's own compositor build (Debian 13 ships the same version)
rm -rf "$R/etc/calamares" "$R/etc/casper.conf" "$R/usr/share/applications/summit-install.desktop" "$R/usr/local/bin/summit-install" "$R"/usr/src/summit-magicmouse-*
ln -sf /usr/bin/picom "$R/usr/local/lib/summitos/picom"
for f in xfce-shapes.svg xfce-x.svg; do      # the desktop's built-in default picture, shown for a moment at first login
  ln -sf /usr/share/backgrounds/summitos/summit-summit-light.jpg "$R/usr/share/backgrounds/xfce/$f"
done
while read -r u; do [ -n "$u" ] && ln -sf /dev/null "$R/etc/systemd/system/$u"; done < "$REPO/build/masked-units.txt"

step "5 system setup"
run bash -c '
set -e
chown lightdm:lightdm /var/lib/lightdm; chmod 750 /var/lib/lightdm
install -d -o lightdm -g lightdm /var/lib/lightdm/.config/gtk-3.0
ln -sf /usr/share/summitos/greeter/gtk.css /var/lib/lightdm/.config/gtk-3.0/gtk.css
python3 /usr/local/lib/summitos/make-icon-themes
for t in /usr/share/icons/Summit-* /usr/share/icons/hicolor; do gtk-update-icon-cache -q -f "$t" || true; done
/usr/local/lib/summitos/bluetooth-setup >/dev/null || true
dconf update; update-desktop-database -q /usr/share/applications || true
plymouth-set-default-theme summit || true
systemctl enable mbpfan zramswap NetworkManager lightdm avahi-daemon earlyoom summit-tune.service 2>/dev/null || true
systemctl disable smbd nmbd ssh ssh.socket NetworkManager-wait-online.service e2scrub_all.timer smartmontools 2>/dev/null || true
systemctl --global enable summit-update-watch.path 2>/dev/null || true
grep -qx applesmc /etc/modules || echo applesmc >> /etc/modules
'
cat > "$R/etc/os-release" <<EOT
PRETTY_NAME="Summit OS $LABEL"
NAME="Summit OS"
ID=summitos
ID_LIKE=debian
VERSION_ID="2.0"
VERSION="$LABEL"
VERSION_CODENAME=trixie
DEBIAN_CODENAME=trixie
HOME_URL="https://github.com/LeaseGeese/summitos"
EOT
echo "Summit OS $LABEL \n \l" > "$R/etc/issue"
ln -sf /usr/share/zoneinfo/America/Denver "$R/etc/localtime"; echo America/Denver > "$R/etc/timezone"
echo summitos > "$R/etc/hostname"
run update-initramfs -u -k all
run dpkg-query -W --showformat='${Package} ${Version}\n' > "$W/manifest.txt"
run bash -c 'apt-get clean; rm -rf /var/lib/apt/lists/* /tmp/* /var/log/*.log /var/log/apt/* /var/cache/debconf/*-old'
rm -f "$R/usr/sbin/policy-rc.d"; : > "$R/etc/machine-id"
proxy_off; umounts; trap - EXIT

step "6 image"
I="$W/iso"; rm -rf "$I"; mkdir -p "$I/live" "$I/.disk"
cp -a "$V2/iso/boot" "$I/"
sed -i "s/Summit OS [0-9.]*\"/Summit OS $LABEL\"/" "$I/boot/grub/themes/summit/theme.txt"
cp "$R/boot/vmlinuz-$KV" "$I/live/vmlinuz"; chmod 644 "$I/live/vmlinuz"; cp "$R/boot/initrd.img-$KV" "$I/live/initrd.img"
touch "$I/summitos.marker"; echo "Summit OS $LABEL - amd64 ($(date +%Y%m%d))" > "$I/.disk/info"
cp "$W/manifest.txt" "$I/live/filesystem.packages"
mksquashfs "$R" "$I/live/filesystem.squashfs" -comp xz -b 1M -Xdict-size 100% -noappend -e boot/grub -quiet
OUT="$W/SummitOS-$FILEVER-amd64.iso"
grub-mkrescue -o "$OUT" "$I" -volid "SUMMITOS_2_0" -- -joliet on 2>/dev/null
( cd "$W" && sha256sum "$(basename "$OUT")" > "$OUT.sha256" )
echo "Built $OUT ($(du -h "$OUT" | cut -f1), $(wc -l < "$W/manifest.txt") packages)"
if [ -n "${SUMMIT_TEST_KEY:-}" ]; then
  # a second image for the build machine's own tests, never published: the same system, plus a start-up
  # hook that lets the build machine sign in to the live session over SSH with this key
  mkdir -p "$I/live/config-hooks"
  cat > "$I/live/config-hooks/test-ssh" <<EOT
#!/bin/sh
install -d -m 700 -o summit -g summit /home/summit/.ssh
echo "$(cat "$SUMMIT_TEST_KEY")" > /home/summit/.ssh/authorized_keys; chown summit:summit /home/summit/.ssh/authorized_keys
ssh-keygen -A >/dev/null 2>&1; systemctl --no-block start ssh
EOT
  chmod +x "$I/live/config-hooks/test-ssh"
  sed -i 's|boot=live components|boot=live components live-config.hooks=file:///run/live/medium/live/config-hooks/test-ssh|' "$I/boot/grub/grub.cfg"
  grub-mkrescue -o "$W/SummitOS-$FILEVER-amd64-TEST.iso" "$I" -volid "SUMMITOS_2_0" -- -joliet on 2>/dev/null
  echo "Built the test image too"
fi
