# Azure Ubuntu Deployment Guide

This guide will help you deploy **Sarral-Scan** (Frontend + Backend) onto a single **Ubuntu 22.04 LTS** Virtual Machine on Azure.

## 1. VM Requirements

- **OS:** Ubuntu Server 22.04 LTS
- **Size:** Standard B2s (2 vCPUs, 4GB RAM) or larger recommended. (Scanning tools can be memory intensive).
- **Networking:** Open inbound ports:
  - `22` (SSH)
  - `80` (HTTP)
  - `443` (HTTPS - optional if setting up SSL)

## 2. Initial Server Setup

SSH into your new VM:

```bash
ssh azureuser@<your-vm-ip>
```

Update system packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget unzip python3-pip python3-venv build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev
```

## 3. Install App Dependencies

### Node.js (v18 or v20)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2
```

### Python 3.10+

Ubuntu 22.04 comes with Python 3.10 by default. Verify:

```bash
python3 --version
```

### Nginx (Web Server)

```bash
sudo apt install -y nginx
```

## 4. Install Security Tools & Wordlists

Since this is a standard Ubuntu VM (not Kali), we must manually install wordlists and specific tool versions.

### A. Wordlists (Crucial)

Create the standard wordlists directory:

```bash
sudo mkdir -p /usr/share/wordlists
sudo chown -R azureuser:azureuser /usr/share/wordlists
```

**1. SecLists (The big one):**

```bash
git clone https://github.com/danielmiessler/SecLists.git /usr/share/wordlists/SecLists
# Create a symlink for easier access if tools expect it elsewhere
sudo ln -s /usr/share/wordlists/SecLists /usr/share/seclists
```

**2. Dirb Wordlists (Common.txt):**

```bash
# Usually comes with dirb, or we can fetch just the lists
mkdir -p /usr/share/wordlists/dirb
wget https://raw.githubusercontent.com/v0re/dirb/master/wordlists/common.txt -O /usr/share/wordlists/dirb/common.txt
```

### B. Standard Tools (APT)

Versions for these are managed by Ubuntu repositories but are generally compatible.

```bash
sudo apt install -y nmap whois dnsutils sslscan sqlmap wafw00f
# Check versions after install:
# nmap --version (Expect ~7.9x)
# sqlmap --version (Expect ~1.6+)
```

### C. Go Setup

```bash
wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz
sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin:~/go/bin' >> ~/.bashrc
source ~/.bashrc
```

### D. Specific Go Tool Versions

We will install the specific versions you requested.

**Subfinder (v2.6.0):**

```bash
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@v2.6.0
```

**Amass (v3.23.3):**
_Note: Amass v4 is the latest, but installing v3 specifically as requested._

```bash
go install -v github.com/owasp-amass/amass/v3/cmd/amass@v3.23.3
```

**Nuclei (v3.4.10):**

```bash
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@v3.4.10
# Download Nuclei Templates
nuclei -update-templates
```

**FFUF (v2.1.0):**

```bash
go install -v github.com/ffuf/ffuf/v2@v2.1.0
```

**Dalfox (v2.12.0):**

```bash
go install -v github.com/hahwul/dalfox/v2@v2.12.0
```

**Assetfinder (Latest - no specific version requested but needed):**

```bash
go install -v github.com/tomnomnom/assetfinder@latest
```

### E. Manual Installs

**WhatWeb:**

```bash
sudo apt install -y ruby ruby-dev
git clone https://github.com/urbanadventurer/WhatWeb.git ~/tools/WhatWeb
# Create a symlink so 'whatweb' command works globally (optional but recommended)
sudo ln -s ~/tools/WhatWeb/whatweb /usr/local/bin/whatweb
```

## 5. Deploy Application

### Clone Repository

```bash
git clone https://github.com/reddy-bhavesh/sarral-scan.git
cd sarral-scan
```

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install prisma
prisma generate

# Environment Variables
cp .env.example .env
nano .env
# UPDATE .env: Set KALI_HOST=localhost if running tools on this same VM. Updates passwords/secrets.
```

### Frontend Setup

```bash
cd ../frontend
npm install
npm run build
# This creates a 'dist' folder
```

## 6. Configure Nginx

Create a site configuration:

```bash
sudo nano /etc/nginx/sites-available/sarral-scan
```

Paste this (replace `your_domain_or_ip`):

```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    # Frontend
    location / {
        root /home/azureuser/sarral-scan/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        # Rewrite /api/(.*) to /$1 before passing to backend if necessary,
        # OR ensure your backend runs on /api prefix.
        # Your FastAPI has prefixes like /auth, /scans.
        # If frontend calls /auth, we need proxy_pass http://localhost:8000/auth;

        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Specific Routes (if /api prefix is not used in frontend calls)
    location ~ ^/(auth|scans|users|events|system|reports) {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE Support
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/sarral-scan /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

## 7. Process Management (PM2)

Start the backend:

```bash
cd ~/sarral-scan/backend
pm2 start "source venv/bin/activate && python -m uvicorn app.main:app --port 8000" --name sarral-backend
```

Save PM2 list to restart on reboot:

```bash
pm2 save
pm2 startup
# Run the command output by pm2 startup
```

## 8. Final Check

Visit `http://<your-vm-ip>` in your browser. You should see the login page.
