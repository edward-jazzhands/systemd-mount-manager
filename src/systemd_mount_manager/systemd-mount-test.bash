# Create a test transient mount
sudo systemd-mount -t tmpfs tmpfs /mnt/test

# Look at what systemd-mount actually generated
cat /run/systemd/transient/mnt-test.mount

# Compare to systemctl's view
systemctl cat mnt-test.mount

# See all properties
systemctl show mnt-test.mount

# Clean up
sudo systemd-umount /mnt/test