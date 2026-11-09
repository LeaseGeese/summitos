#!/bin/bash
# Builds a Summit OS ISO from scratch on Ubuntu 24.04 (needs root, ~30 GB free, about an hour).
#   sudo build/build-iso.sh [workdir]
# Steps: debootstrap Ubuntu noble -> install packages.txt -> apply diversions -> copy overlay ->
#        system tweaks -> squashfs -> bootable BIOS/UEFI ISO.
# Reconstructed from the hand-built 1.21 image (image-manifest.txt lists its exact packages).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
W="${1:-/var/tmp/summitos-build}"; R="$W/chroot"
VERSION=$(python3 -c "import json;print(json.load(open('$REPO/update.json'))['version'])")
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q debootstrap squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools >/dev/null

mkdir -p "$W"
if [ ! -d "$R/etc" ]; then
  debootstrap --arch=amd64 --variant=minbase --components=main,restricted,universe,multiverse noble "$R" http://archive.ubuntu.com/ubuntu/
fi
cat > "$R/etc/apt/sources.list" <<EOF
deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse
EOF
mounts() { for d in proc sys dev dev/pts run; do mountpoint -q "$R/$d" || mount --bind "/$d" "$R/$d"; done; }
umounts() { for d in run dev/pts dev sys proc; do umount -l "$R/$d" 2>/dev/null || true; done; }
trap umounts EXIT; mounts
printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"; chmod +x "$R/usr/sbin/policy-rc.d"
echo 'APT::Install-Recommends "false";' > "$R/etc/apt/apt.conf.d/99norecommends"
echo summitos > "$R/etc/hostname"

# 1. packages
cp "$REPO/build/packages.txt" "$R/tmp/packages.txt"
chroot "$R" bash -c 'apt-get update -q && apt-get -y -q upgrade &&
  apt-get -y -q install locales tzdata && locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8 &&
  xargs -a /tmp/packages.txt apt-get -y -q install && apt-get -y -q purge gnome-shell gnome-shell-common xfdashboard 2>/dev/null; apt-get -y -q autoremove --purge'
ln -sf /usr/share/zoneinfo/America/Denver "$R/etc/localtime"; echo America/Denver > "$R/etc/timezone"

# 2. diversions (moves the package's original aside so Summit's version can take its place)
while read -r from to; do
  [ -n "$from" ] || continue
  chroot "$R" mkdir -p "$(dirname "$to")"
  chroot "$R" dpkg-divert --local --rename --divert "$to" --add "$from" >/dev/null
done < "$REPO/build/diversions.txt"

# 3. Summit files
cp -a "$REPO/overlay/." "$R/"
cp -a "$REPO/build/iso-only/." "$R/"
ln -sf /usr/share/backgrounds/summitos/summit-spectrum-light.jpg "$R/usr/share/backgrounds/xfce/xfce-shapes.svg"
while read -r u; do [ -n "$u" ] && ln -sf /dev/null "$R/etc/systemd/system/$u"; done < "$REPO/build/masked-units.txt"

# 4. system tweaks done inside the image
chroot "$R" bash -c '
set -e
chown lightdm:lightdm /var/lib/lightdm; chmod 750 /var/lib/lightdm
install -d -o lightdm -g lightdm /var/lib/lightdm/.config/gtk-3.0
ln -sf /usr/share/summitos/greeter/gtk.css /var/lib/lightdm/.config/gtk-3.0/gtk.css
python3 /usr/local/lib/summitos/make-icon-themes
for t in /usr/share/icons/Summit-* /usr/share/icons/hicolor; do gtk-update-icon-cache -q -f "$t" || true; done
dconf update; update-desktop-database -q /usr/share/applications || true
plymouth-set-default-theme summit || true
systemctl enable mbpfan zramswap NetworkManager lightdm avahi-daemon earlyoom summit-update.timer 2>/dev/null || true
systemctl disable smbd ssh ssh.socket NetworkManager-wait-online.service motd-news.timer e2scrub_all.timer smartmontools udisks2 2>/dev/null || true
systemctl --global enable summit-update-watch.path 2>/dev/null || true
echo applesmc >> /etc/modules
'
sed -i "s/^PRETTY_NAME=.*/PRETTY_NAME=\"Summit OS $VERSION (Ubuntu 24.04 base)\"/" "$R/etc/os-release"
sed -i "s/^DISTRIB_DESCRIPTION=.*/DISTRIB_DESCRIPTION=\"Summit OS $VERSION\"/" "$R/etc/lsb-release"
chroot "$R" update-initramfs -u -k all
chroot "$R" bash -c 'apt-get clean; rm -rf /var/lib/apt/lists/* /tmp/*'
rm -f "$R/usr/sbin/policy-rc.d"; : > "$R/etc/machine-id"
umounts; trap - EXIT

# 5. ISO
I="$W/iso"; rm -rf "$I"; mkdir -p "$I/casper" "$I/.disk"
cp -a "$REPO/build/iso/boot" "$I/"
sed -i "s/Summit OS [0-9.]*\"/Summit OS $VERSION\"/" "$I/boot/grub/themes/summit/theme.txt"
K=$(ls "$R"/boot/vmlinuz-* | sort -V | tail -1); cp "$K" "$I/casper/vmlinuz"; chmod 644 "$I/casper/vmlinuz"
cp "$R/boot/initrd.img-${K##*vmlinuz-}" "$I/casper/initrd"
touch "$I/summitos.marker"; echo "Summit OS $VERSION - amd64 ($(date +%Y%m%d))" > "$I/.disk/info"
chroot "$R" dpkg-query -W --showformat='${Package} ${Version}\n' > "$I/casper/filesystem.manifest"
mksquashfs "$R" "$I/casper/filesystem.squashfs" -comp xz -b 1M -Xdict-size 100% -noappend -e boot/grub -quiet
du -sx --block-size=1 "$R" | cut -f1 > "$I/casper/filesystem.size"
grub-mkrescue -o "$W/SummitOS-$VERSION-amd64.iso" "$I" -volid "SUMMITOS_${VERSION//./_}" -- -joliet on
echo "Built $W/SummitOS-$VERSION-amd64.iso"
