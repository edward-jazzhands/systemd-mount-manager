%pre
if ! command -v systemctl &> /dev/null; then
    echo "ERROR: systemd is not installed or not running on this system."
    echo "systemd-mount-manager requires systemd to function."
    exit 1
fi

if [ ! -d /run/systemd/system ]; then
    echo "ERROR: systemd is not the active init system."
    echo "systemd-mount-manager requires systemd to function."
    exit 1
fi


# fix me
# install -D -m 644 data/com.yourname.mountmanager.policy %{buildroot}/usr/share/polkit-1/actions/