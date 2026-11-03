# 🚀 Deploying VedioHooks AI on Oracle Cloud Always Free (Ampere A1)

This guide provides a comprehensive, production-grade walkthrough for deploying **VedioHooks AI** on Oracle Cloud Infrastructure (OCI) **100% Always Free Tier**.

---

## 💎 Free Tier Specifications

Oracle Cloud offers the most generous free tier in the cloud computing industry:

| Resource | Always Free Allocation | VedioHooks AI Usage |
| :--- | :--- | :--- |
| **Compute Architecture** | Ampere A1 ARM64 (`VM.Standard.A1.Flex`) | **4 OCPUs** (Full Power) |
| **System Memory** | 24 GB RAM | **24 GB RAM** (Sufficient for Faster-Whisper + FFmpeg + OpenCV) |
| **Storage** | 200 GB NVMe Disk | **100–150 GB** (Storage for source videos & vertical shorts) |
| **Bandwidth** | 10 TB / month Outbound | Unlimited Free Inbound + Plenty of Shorts Delivery |
| **Operating System** | Canonical Ubuntu 24.04 / 22.04 LTS | Ubuntu Linux |
| **Cost** | **$0.00 / month forever** | **100% Free** |

---

## Step 1: Create Your Oracle Cloud Account

1. Go to [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) and sign up.
2. Select your **Home Region** (choose the one geographically closest to you, e.g., *US East (Ashburn)*, *US West (Phoenix)*, *Frankfurt*, *Mumbai*, etc.).
3. A credit card is required for identity verification (Oracle places a temporary \$1 hold that is immediately refunded). No charges will ever occur as long as you stay within the **Always Free** limits.

---

## Step 2: Provision the Ampere A1 Compute Instance

1. Log into your **OCI Console**.
2. Click the hamburger menu (≡) in the top-left corner and navigate to **Compute > Instances**.
3. Click **Create Instance**.
4. Configure the instance settings:
   - **Name:** `vediohooks-ai`
   - **Placement:** Keep default Availability Domain.
   - **Image and Shape:**
     - Click **Change Image**: Select **Canonical Ubuntu 24.04** (or Ubuntu 22.04).
     - Click **Change Shape**:
       - Select **Ampere** (Arm-based processor).
       - Choose **VM.Standard.A1.Flex**.
       - Drag the sliders to:
         - **OCPUs:** `4`
         - **Memory (GB):** `24`
   - **Networking:**
     - Select **Create new virtual cloud network (VCN)**.
     - Ensure **Assign a public IPv4 address** is checked (**Yes**).
   - **Add SSH Keys:**
     - Select **Generate a key pair for me** and click **Save Private Key** (download the `.key` file to your computer) AND **Save Public Key**.
     - *Or* select **Upload public key files** if you already have an `id_rsa.pub`.
   - **Boot Volume:**
     - Check **Specify a custom boot volume size**.
     - Set size to **100 GB** or **150 GB** (up to 200 GB is free).
5. Click **Create**. The instance will say `PROVISIONING` and turn `RUNNING` within 1–2 minutes.
6. Note down your **Public IP Address** (e.g., `129.153.xx.xx`).

---

## Step 3: Configure Oracle Cloud Firewall (VCN Ingress Rules)

> [!IMPORTANT]
> By default, Oracle Cloud blocks all incoming traffic except SSH (port 22). You **must** open Port 80, Port 443, and Port 8000 in your OCI Security List, otherwise you will not be able to access the dashboard in your browser.

1. In the instance details page, under **Instance Information**, click on your **Virtual Cloud Network** link (e.g., `vcn-xxxx`).
2. On the left side under **Resources**, click **Security Lists**.
3. Click on the **Default Security List for vcn-xxxx**.
4. Click **Add Ingress Rules**.
5. Add the following rules:

### Ingress Rule 1: HTTP (Port 80)
- **Source CIDR:** `0.0.0.0/0`
- **IP Protocol:** `TCP`
- **Destination Port Range:** `80`
- **Description:** `VedioHooks AI HTTP Web Dashboard`

### Ingress Rule 2: HTTPS (Port 443)
- **Source CIDR:** `0.0.0.0/0`
- **IP Protocol:** `TCP`
- **Destination Port Range:** `443`
- **Description:** `VedioHooks AI HTTPS SSL Proxy`

### Ingress Rule 3: API Direct (Port 8000)
- **Source CIDR:** `0.0.0.0/0`
- **IP Protocol:** `TCP`
- **Destination Port Range:** `8000`
- **Description:** `VedioHooks AI FastAPI Direct Backend`

6. Click **Add Ingress Rules**.

---

## Step 4: Connect to Your VM via SSH

Open **PowerShell** or **Terminal** on your local machine:

```powershell
# Set strict permissions on your private key (Windows PowerShell)
icacls "C:\path\to\your_private_key.key" /inheritance:r
icacls "C:\path\to\your_private_key.key" /grant:r "$($env:USERNAME):(R)"

# Or on Linux / macOS:
# chmod 400 path/to/your_private_key.key

# Connect to the instance
ssh -i "C:\path\to\your_private_key.key" ubuntu@<YOUR_PUBLIC_IP>
```

---

## Step 5: Run Automated 1-Command Deployment

Once connected to your Ubuntu VM:

### Option A: Clone via Git
```bash
# Clone the repository
git clone https://github.com/your-username/Vedio_Hooks.git
cd Vedio_Hooks

# Make the deploy script executable and run it
chmod +x deployment/oracle/deploy.sh
./deployment/oracle/deploy.sh
```

### Option B: Upload from Your Windows Machine via SCP
If your code is local on Windows:
```powershell
# Run from your local Windows PowerShell inside your project folder:
scp -i "C:\path\to\your_private_key.key" -r * ubuntu@<YOUR_PUBLIC_IP>:/home/ubuntu/Vedio_Hooks/
```
Then on the VM:
```bash
cd /home/ubuntu/Vedio_Hooks
chmod +x deployment/oracle/deploy.sh
./deployment/oracle/deploy.sh
```

---

## What the Automated Script Does

The deployment script executes the complete setup unattended:
1. Installs system multimedia tools (`ffmpeg`, `libgl1`, `libglib2.0-0`, `build-essential`).
2. Configures the Ubuntu internal `iptables` and `ufw` firewall to accept traffic on ports 80, 443, and 8000.
3. Sets up an isolated Python 3 virtual environment (`.venv`) and installs all requirements.
4. Creates persistent media directories (`temp/`, `output/`, `models/`).
5. Configures two autonomous Systemd services:
   - `vediohooks-web.service`: Runs the FastAPI server with Uvicorn (2 workers, reverse-proxied).
   - `vediohooks-scheduler.service`: Runs the 24/7 autonomous job scheduler daemon.
6. Configures Nginx reverse proxy with:
   - **1 GB file upload support** for high-resolution video ingestion.
   - **600-second timeouts** for extended video rendering tasks.
   - **WebSocket pass-through** for real-time progress updates.
   - **Gzip compression** for snappy dashboard responsiveness.

---

## Step 6: Access Your VedioHooks AI Factory

Once the script finishes:

- **Web Dashboard:** `http://<YOUR_PUBLIC_IP>/`
- **Interactive API Docs:** `http://<YOUR_PUBLIC_IP>:8000/docs`
- **System Telemetry:** `http://<YOUR_PUBLIC_IP>/api/v1/system/telemetry`

---

## Step 7: (Optional) Add Free Custom Domain & SSL (HTTPS)

If you own a domain (e.g., `vediohooks.yourdomain.com`):

1. Add a DNS **A Record** pointing your domain to `<YOUR_PUBLIC_IP>`.
2. On your VM, run Certbot:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d vediohooks.yourdomain.com
```
3. Certbot will automatically issue a free Let's Encrypt certificate and reconfigure Nginx for HTTPS. Auto-renewal is set up out of the box.

---

## Day-2 Operations & Service Management

### Check Service Status
```bash
# Check Web Server
sudo systemctl status vediohooks-web

# Check 24/7 Scheduler Daemon
sudo systemctl status vediohooks-scheduler

# Check Nginx
sudo systemctl status nginx
```

### View Live Logs
```bash
# Stream Web Server Logs
sudo journalctl -u vediohooks-web -f

# Stream Background Scheduler Logs
sudo journalctl -u vediohooks-scheduler -f
```

### Restart Services
```bash
sudo systemctl restart vediohooks-web
sudo systemctl restart vediohooks-scheduler
```

### Update to Latest Code
```bash
cd /home/ubuntu/Vedio_Hooks
git pull
sudo systemctl restart vediohooks-web vediohooks-scheduler
```

---

## Troubleshooting & Tips

### 1. "Out of Capacity" when creating Ampere A1 instance
Ampere A1 instances are extremely popular. If you see an `Out of host capacity` error:
- Try changing the **Availability Domain** (AD-1, AD-2, or AD-3).
- Try setting OCPUs to `2` and Memory to `12 GB` initially, then scale up to 4 / 24 GB later.
- Try creating it during off-peak hours (e.g., early morning).

### 2. Dashboard doesn't load in browser
- **Check Oracle Cloud Security List:** Ensure Port 80 is open to `0.0.0.0/0` in Ingress Rules (Step 3).
- **Check OS Firewall:** Run `sudo iptables -L -n -v` to ensure port 80 has an ACCEPT rule (handled automatically by `deploy.sh`).
- **Check Services:** Run `sudo systemctl status vediohooks-web` and `sudo systemctl status nginx`.

### 3. Database & Media Backup
The SQLite database is located at `/home/ubuntu/Vedio_Hooks/jobs.db`.
The built-in automated backup system backs up `jobs.db` regularly. To copy it locally:
```powershell
scp -i "C:\path\to\your_private_key.key" ubuntu@<YOUR_PUBLIC_IP>:/home/ubuntu/Vedio_Hooks/jobs.db ./jobs_backup.db
```

