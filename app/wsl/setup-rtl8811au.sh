#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y build-essential bc flex bison dwarves libssl-dev libelf-dev unzip iw tcpdump usbutils
release="$(uname -r)"
version="${release%%-microsoft*}"
if [ "$version" != "6.6.87.2" ]; then
  echo "The portable package contains kernel source 6.6.87.2, but WSL is using $version. A matching source bundle or a newer WSL kernel with built-in rtw88_8821au support is required." >&2
  exit 2
fi
src="/usr/src/WSL2-Linux-Kernel-$version"
bundle="$(cd "$(dirname "$0")/../vendor/wsl-bundle" && pwd)"
if [ ! -d "$src/Microsoft" ]; then
  rm -rf "$src"
  unzip -q "$bundle/WSL2-Linux-Kernel-6.6.87.2.zip" -d /usr/src
  extracted="$(find /usr/src -maxdepth 1 -type d -name 'WSL2-Linux-Kernel-linux-msft-wsl-*' | head -1)"
  mv "$extracted" "$src"
fi
cd "$src"
make KCONFIG_CONFIG=Microsoft/config-wsl olddefconfig
make KCONFIG_CONFIG=Microsoft/config-wsl modules_prepare -j"$(nproc)"
ln -sfn "$src" "/lib/modules/$release/build"
driver=/usr/src/rtw88-rf-traffic-monitor
if [ ! -f "$driver/Makefile" ]; then
  rm -rf "$driver"
  unzip -q "$bundle/rtw88-master.zip" -d /usr/src
  mv /usr/src/rtw88-master "$driver"
fi
cd "$driver"
make clean
make -j"$(nproc)" KSRC="$src"
make install KSRC="$src"
make install_fw
depmod -a
modprobe cfg80211
modprobe mac80211
modprobe rtw_8821au
echo '{"status":"done","driver":"rtw_8821au"}'
