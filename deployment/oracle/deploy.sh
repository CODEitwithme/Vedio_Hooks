#!/usr/bin/env bash
# ==============================================================================
# VedioHooks AI - Automated Oracle Cloud Always Free Deployment Script
# Target: Ubuntu 22.04 / 24.04 LTS on Ampere A1 (ARM64) or x86_64
# ==============================================================================

set -e

# Visual colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}        🚀 VedioHooks AI - Automated Oracle Cloud Deployment Script           ${NC}"
echo -e "${BLUE}==============================================================================${NC}"

# Detect project directory and current user
INSTALL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CURRENT_USER=$(whoami)

echo -e "[*] Project directory: ${GREEN}${INSTALL_DIR}${NC}"
echo -e "[*] Deployment user:   ${GREEN}${CURRENT_USER}${NC}"

# 1. Update OS package indices & install dependencies
echo -e "\n${YELLOW}[1/7] Updating system packages & installing core multimedia dependencies...${NC}"
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    ffmpeg \
    nginx \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    iptables-persistent \
    netfilter-persistent

# 2. Configure Oracle Cloud Linux OS Firewall (iptables & ufw)
echo -e "\n${YELLOW}[2/7] Configuring OS firewall rules for Ports 80, 443, and 8000...${NC}"
# Oracle Cloud Ubuntu images ship with strict preconfigured iptables rules
sudo iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

# Also configure UFW if enabled
if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 80/tcp 2>/dev/null || true
    sudo ufw allow 443/tcp 2>/dev/null || true
    sudo ufw allow 8000/tcp 2>/dev/null || true
fi

# 3. Create required runtime directories
echo -e "\n${YELLOW}[3/7] Initializing runtime directories...${NC}"
mkdir -p "${INSTALL_DIR}/temp"
mkdir -p "${INSTALL_DIR}/output"
mkdir -p "${INSTALL_DIR}/models"
chmod 775 "${INSTALL_DIR}/temp" "${INSTALL_DIR}/output" "${INSTALL_DIR}/models"

# 4. Set up Python virtual environment
echo -e "\n${YELLOW}[4/7] Setting up Python virtual environment and dependencies...${NC}"
cd "${INSTALL_DIR}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 5. Configure Systemd Services
echo -e "\n${YELLOW}[5/7] Installing Systemd microservices (Web + 24/7 Scheduler)...${NC}"

# Configure Web Service
WEB_SERVICE_SRC="${INSTALL_DIR}/deployment/oracle/vediohooks-web.service"
WEB_SERVICE_DEST="/etc/systemd/system/vediohooks-web.service"
sudo cp "${WEB_SERVICE_SRC}" "${WEB_SERVICE_DEST}"
# Update working directory and user dynamically if needed
sudo sed -i "s|/home/ubuntu/Vedio_Hooks|${INSTALL_DIR}|g" "${WEB_SERVICE_DEST}"
sudo sed -i "s|User=ubuntu|User=${CURRENT_USER}|g" "${WEB_SERVICE_DEST}"

# Configure Scheduler Service
SCHED_SERVICE_SRC="${INSTALL_DIR}/deployment/oracle/vediohooks-scheduler.service"
SCHED_SERVICE_DEST="/etc/systemd/system/vediohooks-scheduler.service"
sudo cp "${SCHED_SERVICE_SRC}" "${SCHED_SERVICE_DEST}"
sudo sed -i "s|/home/ubuntu/Vedio_Hooks|${INSTALL_DIR}|g" "${SCHED_SERVICE_DEST}"
sudo sed -i "s|User=ubuntu|User=${CURRENT_USER}|g" "${SCHED_SERVICE_DEST}"

sudo systemctl daemon-reload
sudo systemctl enable vediohooks-web.service
sudo systemctl enable vediohooks-scheduler.service
sudo systemctl restart vediohooks-web.service
sudo systemctl restart vediohooks-scheduler.service

# 6. Configure Nginx Reverse Proxy
echo -e "\n${YELLOW}[6/7] Configuring Nginx reverse proxy...${NC}"
NGINX_CONF_SRC="${INSTALL_DIR}/deployment/oracle/nginx.conf"
NGINX_CONF_DEST="/etc/nginx/sites-available/vediohooks"

sudo cp "${NGINX_CONF_SRC}" "${NGINX_CONF_DEST}"
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf "${NGINX_CONF_DEST}" /etc/nginx/sites-enabled/vediohooks

sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# 7. Verification & Status Check
echo -e "\n${YELLOW}[7/7] Validating deployment health...${NC}"
sleep 3

# Fetch Public IP
PUBLIC_IP=$(curl -s https://ifconfig.me || curl -s https://api.ipify.org || echo "YOUR_SERVER_IP")

echo -e "\n${GREEN}==============================================================================${NC}"
echo -e "${GREEN}       🎉 VedioHooks AI Successfully Deployed to Oracle Cloud Always Free!    ${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo -e "\nWeb Dashboard:     ${BLUE}http://${PUBLIC_IP}/${NC}"
echo -e "Direct API:        ${BLUE}http://${PUBLIC_IP}:8000/docs${NC}"
echo -e "Health Check:      ${BLUE}http://${PUBLIC_IP}/api/v1/system/telemetry${NC}"
echo -e "\nManage Services:"
echo -e "  Web Service:       ${YELLOW}sudo systemctl status vediohooks-web${NC}"
echo -e "  Scheduler Daemon:  ${YELLOW}sudo systemctl status vediohooks-scheduler${NC}"
echo -e "  Nginx Proxy:       ${YELLOW}sudo systemctl status nginx${NC}"
echo -e "  Web Logs:          ${YELLOW}sudo journalctl -u vediohooks-web -f${NC}"
echo -e "  Scheduler Logs:    ${YELLOW}sudo journalctl -u vediohooks-scheduler -f${NC}"
echo -e "\n${YELLOW}IMPORTANT: Ensure Port 80 and 8000 are open in your Oracle Cloud Virtual Cloud Network (VCN) Ingress Security Rules!${NC}\n"

