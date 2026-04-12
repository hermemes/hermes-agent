#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════╗"
echo "║   ☤  HERMEMES VPS SETUP                      ║"
echo "╚══════════════════════════════════════════════╝"

# Update system
echo "[1/6] Updating system..."
apt update && apt upgrade -y

# Install dependencies
echo "[2/6] Installing dependencies..."
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git ufw

# Create app user
echo "[3/6] Creating hermemes user..."
if ! id "hermemes" &>/dev/null; then
    useradd -m -s /bin/bash hermemes
    echo "User 'hermemes' created"
else
    echo "User 'hermemes' already exists"
fi

# Clone repo
echo "[4/6] Cloning repository..."
APP_DIR="/home/hermemes/hermes-agent"
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR" && git pull
else
    git clone https://github.com/hermemes/hermes-agent.git "$APP_DIR"
fi
chown -R hermemes:hermemes "$APP_DIR"

# Setup firewall
echo "[5/6] Configuring firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# Install systemd service
echo "[6/6] Installing systemd service..."
cp "$APP_DIR/deploy/hermemes.service" /etc/systemd/system/hermemes.service
systemctl daemon-reload
systemctl enable hermemes

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Copy your nginx config:  cp $APP_DIR/deploy/hermemes-nginx.conf /etc/nginx/sites-available/hermemes"
echo "  2. Enable it:               ln -sf /etc/nginx/sites-available/hermemes /etc/nginx/sites-enabled/hermemes"
echo "  3. Remove default:          rm -f /etc/nginx/sites-enabled/default"
echo "  4. Test nginx:              nginx -t"
echo "  5. Restart nginx:           systemctl restart nginx"
echo "  6. Create .env file:        nano $APP_DIR/.env"
echo "  7. Start hermemes:          systemctl start hermemes"
echo "  8. Check status:            systemctl status hermemes"
echo ""
echo "For SSL (if you have a domain):"
echo "  certbot --nginx -d yourdomain.com"
