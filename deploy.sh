#!/bin/bash
# ============================================================
#   VEO3 License Server - Auto Deploy Script
#   Chay tren VPS Ubuntu 20.04/22.04/24.04
# ============================================================

set -e

echo "======================================================"
echo "   VEO3 LICENSE SERVER - AUTO DEPLOY"
echo "======================================================"

# 1. Cap nhat he thong
echo "[1/6] Cap nhat he thong..."
sudo apt update && sudo apt upgrade -y

# 2. Cai Python 3.11+
echo "[2/6] Cai Python..."
sudo apt install -y python3 python3-pip python3-venv curl ufw

# 3. Tao thu muc va virtual environment
echo "[3/6] Tao thu muc ung dung..."
sudo mkdir -p /opt/veo3-api
sudo chown $USER:$USER /opt/veo3-api

# Copy backend vào /opt/veo3-api/ truoc khi chay script nay
cd /opt/veo3-api
python3 -m venv venv
source venv/bin/activate

# 4. Cai dependencies
echo "[4/6] Cai dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Tao file .env (NEU CHUA CO)
if [ ! -f .env ]; then
    echo "[5/6] Tao file .env..."
    
    # Tao RSA keys cho JWT
    openssl genrsa -out /tmp/private.pem 2048
    openssl rsa -in /tmp/private.pem -pubout -out /tmp/public.pem
    PRIVATE_KEY=$(cat /tmp/private.pem)
    PUBLIC_KEY=$(cat /tmp/public.pem)
    SECRET=$(openssl rand -hex 32)
    
    cat > .env << ENVEOF
DATABASE_URL=sqlite+aiosqlite:///./quanlykey.db
SECRET_KEY=${SECRET}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_PRIVATE_KEY="""${PRIVATE_KEY}"""
JWT_PUBLIC_KEY="""${PUBLIC_KEY}"""
MIN_VERSION=1.2.62
MAINTENANCE_MODE=false
ENVEOF
    
    rm /tmp/private.pem /tmp/public.pem
    echo "[+] Da tao .env voi RSA keys moi"
else
    echo "[5/6] File .env da ton tai, bo qua"
fi

# 6. Tao systemd service
echo "[6/6] Tao systemd service..."
sudo tee /etc/systemd/system/veo3-api.service > /dev/null << EOF
[Unit]
Description=VEO3 License Management API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/veo3-api
Environment=PATH=/opt/veo3-api/venv/bin
ExecStart=/opt/veo3-api/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable veo3-api
sudo systemctl start veo3-api

# Mo firewall
sudo ufw allow 8000/tcp

echo ""
echo "======================================================"
echo "   DEPLOY THANH CONG!"
echo "======================================================"
echo "   API: http://$(curl -s ifconfig.me):8000"
echo "   Docs: http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "   Lenh quan ly:"
echo "   - Xem trang thai: sudo systemctl status veo3-api"
echo "   - Xem log:        sudo journalctl -u veo3-api -f"
echo "   - Restart:        sudo systemctl restart veo3-api"
echo "======================================================"
