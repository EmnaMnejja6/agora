#!/usr/bin/env bash
# Creates the OPNsense VM for site A (2 NICs, 20 GB disk, ISO attached).
# Usage: ./create_vm.sh /path/to/OPNsense-xx-dvd-amd64.iso[.bz2]
# Optional: WAN_IF="<Windows adapter name>" ./create_vm.sh ...
set -euo pipefail

VB() { VBoxManage.exe "$@"; }                                              # CHANGED (added)

VM="site_a_opnsense"
ISO="${1:?Usage: $0 /mnt/d/OPNsense-26.7-dvd-amd64.iso}"
WAN_IF="${WAN_IF:-Realtek RTL8852BE WiFi 6 802.11ax PCIe Adapter}"         # CHANGED (:- instead of :)
LAN_NET="LAN-A"              # must match the Vagrantfile
RAM_MB=3072
CPUS=2
DISK_MB=20480
BASE="/mnt/d/VirtualBox VMs"

# 1. Check the ISO (decompress if needed)
[ -f "$ISO" ] || { echo "File not found: $ISO"; exit 1; }
if [[ "$ISO" == *.bz2 ]]; then
  echo "Decompressing $ISO ..."
  bunzip2 -k "$ISO"
  ISO="${ISO%.bz2}"
fi
[[ "$ISO" == *.iso ]] || { echo "Not an .iso file: $ISO"; exit 1; }
ISO="$(realpath "$ISO")"

ISO_WIN="$(wslpath -w "$ISO")"                                             # CHANGED (added)
mkdir -p "$BASE"                                                           # CHANGED (added)
BASE_WIN="$(wslpath -w "$BASE")"                                           # CHANGED (added)

# 2. Refuse to overwrite an existing VM
if VB list vms | grep -q "\"$VM\""; then
  echo "VM $VM already exists. Remove it with:"
  echo "  VBoxManage.exe unregistervm $VM --delete"
  exit 1
fi

# 3. Create the VM (fall back to a generic type if FreeBSD_64 is refused)
VB createvm --name "$VM" --basefolder "$BASE_WIN" --register \
  --ostype FreeBSD_64 2>/dev/null \
|| VB createvm --name "$VM" --basefolder "$BASE_WIN" --register \
  --ostype Other_64

# 4. Hardware: BIOS boot, PIIX3 chipset, APIC on
VB modifyvm "$VM" \
  --memory "$RAM_MB" --cpus "$CPUS" \
  --firmware bios --chipset piix3 --ioapic on \
  --graphicscontroller vmsvga --vram 16 \
  --boot1 dvd --boot2 disk --boot3 none --boot4 none

# 5. Network: NIC1 = WAN (bridged), NIC2 = LAN (NAT Network, same as the 4 VMs)
VB modifyvm "$VM" \
  --nic1 bridged --bridgeadapter1 "$WAN_IF" --nictype1 82540EM --nicpromisc1 allow-all \
  --nic2 natnetwork --nat-network2 "$LAN_NET" --nictype2 82540EM --nicpromisc2 allow-all   # CHANGED (intnet -> natnetwork)

# 6. Disk and ISO
VB createmedium disk --filename "$BASE_WIN\\$VM\\$VM.vdi" --size "$DISK_MB" --format VDI
VB storagectl "$VM" --name SATA --add sata --controller IntelAhci
VB storageattach "$VM" --storagectl SATA --port 0 --device 0 \
  --type hdd --medium "$BASE_WIN\\$VM\\$VM.vdi"
VB storageattach "$VM" --storagectl SATA --port 1 --device 0 \
  --type dvddrive --medium "$ISO_WIN"

echo
echo "VM $VM created."
echo "  WAN  : bridged on $WAN_IF"
echo "  LAN  : NAT Network $LAN_NET"
echo "Start it with: VBoxManage.exe startvm $VM --type gui"