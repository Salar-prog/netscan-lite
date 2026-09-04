#!/usr/bin/env bash
set -euo pipefail

echo "Installing ns-lite..."

# Create system user
if ! id -r ns-lite >/dev/null 2>&1; then
    useradd -r -s /sbin/nologin -d /home/ns-lite ns-lite
    echo "Created user: ns-lite"
fi

# Create venv and install Python package
python3 -m venv /opt/ns-lite/venv
/opt/ns-lite/venv/bin/pip install --upgrade pip
/opt/ns-lite/venv/bin/pip install -e ".[xlsx,postgres]"
echo "Installed ns-lite Python package"

# Create wrapper script that uses the venv
cat > /opt/ns-lite/venv/bin/ns-lite-wrapper << 'WRAPPER'
#!/usr/bin/env bash
exec /opt/ns-lite/venv/bin/ns-lite "$@"
WRAPPER
chmod +x /opt/ns-lite/venv/bin/ns-lite-wrapper

# Create directories
mkdir -p /opt/ns-lite/data /home/ns-lite/.ns-lite
chown -R ns-lite:ns-lite /opt/ns-lite /home/ns-lite/.ns-lite

# Copy systemd service
cp deploy/ns-lite.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ns-lite

echo ""
echo "ns-lite installed successfully."
echo ""
echo "Next steps:"
echo "  1. Copy and edit the environment file:"
echo "     cp .env.production /opt/ns-lite/.env"
echo "     nano /opt/ns-lite/.env"
echo ""
echo "  2. Start the service:"
echo "     systemctl start ns-lite"
echo ""
echo "  3. Check status:"
echo "     systemctl status ns-lite"
echo "     curl http://localhost:8000/health"
