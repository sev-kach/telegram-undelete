# Setting Up a Free Cloud Server on Oracle Cloud

This guide walks you through creating a **free, permanent server** on Oracle Cloud to run lightweight apps (like a Telegram bot) 24/7 without paying anything. No cloud experience needed.

---

## What You Get (Free Forever)

Oracle Cloud offers an "Always Free" tier that **never expires and never charges you**:

- **1 small server** (VM.Standard.E2.1.Micro — 1 CPU, 1 GB RAM)
- **46 GB storage**
- **10 TB/month data transfer**
- Runs Ubuntu Linux (like a regular computer, just in the cloud)

This is more than enough for running Python scripts, bots, small web apps, or background monitoring tools.

> A credit card is required during sign-up for identity verification only. You will NOT be charged.

---

## Step-by-Step Setup

### 1. Create an Oracle Cloud Account

1. Go to **https://www.oracle.com/cloud/free/**
2. Click **"Start for free"**
3. Fill in your details (name, email, country)
4. Choose a **Home Region** — this is where your server will live. Pick the one closest to you geographically:
   - For Europe: Amsterdam, Frankfurt, Stockholm, Marseille, or Milan
   - For US: Ashburn, Phoenix, Chicago, or San Jose
   - For Asia: Osaka, Tokyo, Seoul, Mumbai, or Singapore
5. Set a password (must have uppercase, lowercase, number, and special character)
6. Enter credit card for verification (you will NOT be charged)
7. Complete the sign-up

### 2. Create a Virtual Machine (Server)

1. Log in at **https://cloud.oracle.com**
2. Click the **hamburger menu** (three lines, top left) → **Compute** → **Instances**
3. Click **"Create Instance"**

#### Configure the instance:

**Name:** Leave the default or type something like `telegram-bot`

**Image:** Click Edit → Select **Canonical Ubuntu 22.04** (or 24.04 if available)

**Shape (server size):** Click Edit → Choose:
- Tab: **"Specialty and previous generation"**
- Select: **VM.Standard.E2.1.Micro**
- This is the Always Free x86 instance (1 CPU, 1 GB RAM)

> **Why not the ARM shape?** Oracle also offers free ARM servers (VM.Standard.A1.Flex — up to 4 CPUs, 24 GB RAM), which are more powerful. However, popular regions like Amsterdam, Frankfurt, and London are often **out of capacity** for ARM. If you see the error "Out of capacity for shape VM.Standard.A1.Flex", switch to the x86 Micro shape instead. It's smaller but always available.

**Networking:**
- Select **"Create new virtual cloud network"**
- Select **"Create new public subnet"**
- Check **"Automatically assign public IPv4 address"** — this gives your server an IP address so you can connect to it

> **If the public IP checkbox is greyed out:** Make sure you selected "Create new **public** subnet" (not private). If it still won't work, create the instance without a public IP — you can add one afterwards from the Networking page.

**SSH Keys (important!):**
- Select **"Generate a key pair for me"**
- Click **"Save private key"** — this downloads a `.key` file to your computer
- **Keep this file safe!** It's the only way to access your server. If you lose it, you'll need to create a new server.

**Storage:** Leave all defaults (46.6 GB boot volume, no encryption changes needed)

**Security:** Leave all defaults (skip shielded instances and confidential computing)

4. Click **"Create"**
5. Wait 1-2 minutes for the server to start
6. On the instance details page, find the **Public IP Address** (looks like `129.xxx.xxx.xxx`) — you'll need this

### 3. Connect to Your Server

**On Windows (PowerShell):**
```
ssh -i C:\Users\YourName\Downloads\ssh-key-2026-04-18.key ubuntu@YOUR_PUBLIC_IP
```

**On Mac/Linux (Terminal):**
```
chmod 400 ~/Downloads/ssh-key-2026-04-18.key
ssh -i ~/Downloads/ssh-key-2026-04-18.key ubuntu@YOUR_PUBLIC_IP
```

Replace `YOUR_PUBLIC_IP` with the IP address from step 6 above.

> First time connecting, it will ask "Are you sure you want to continue connecting?" — type `yes`.

You're now logged into your free cloud server.

---

## Common Issues and Solutions

### "Out of capacity for shape VM.Standard.A1.Flex"

**Problem:** The free ARM servers are very popular. Busy regions (Amsterdam, Frankfurt, London) often have no capacity.

**Solutions (try in order):**
1. Switch to **VM.Standard.E2.1.Micro** (x86) — smaller but always available
2. Try a different availability domain (AD-2 or AD-3 if available)
3. Try again later (capacity changes throughout the day)
4. Switch to a less popular region (Marseille, Stockholm, Osaka, Sao Paulo) — but Oracle limits free accounts to 1-2 regions

### "Maximum number of regions exceeded"

**Problem:** Oracle free accounts can only use a limited number of regions. You can't add more.

**Solution:** Use your home region (the one you picked during sign-up). Don't try to add new regions.

### "Public IPv4 address checkbox is greyed out"

**Problem:** The subnet type needs to be public for a public IP.

**Solutions:**
1. Make sure you selected **"Create new public subnet"** (not "Select existing subnet")
2. If still greyed out, create the instance without a public IP, then:
   - Go to **Networking** → **Virtual Cloud Networks** → your VCN → your subnet
   - Check that the subnet type is "Public"
   - Go back to your instance → **Attached VNICs** → click the VNIC → **IPv4 Addresses** → **Edit** → assign a public IP

### Instance created but state is "Stopped"

**Problem:** After clicking "Create", the instance doesn't start automatically.

**Solution:** Go to the instance details page and click the **"Start"** button. Wait 1-2 minutes for the state to change from "Starting" to "Running".

### Public IP shows "—" (empty) after creation

**Problem:** The instance was created without a public IP address, usually because the public IP checkbox was greyed out during creation.

**Solution:**
1. Wait for the instance state to show **"Running"**
2. On the instance details page, click the **"Networking"** tab
3. Under **"Attached VNICs"**, click on the VNIC name (it will have the same name as your instance)
4. Click **"IPv4 Addresses"** on the left menu
5. Click the **three dots menu** (⋮) next to the private IP
6. Click **"Edit"**
7. Under "Public IPv4 address", select **"Ephemeral public IP"**
8. Click **"Update"**
9. A public IP address will appear — copy it for SSH access

### "Permission denied (publickey)" when connecting via SSH

**Problem:** The SSH key file has wrong permissions or wrong path.

**Solutions:**
- Make sure you're using the correct `.key` file you downloaded
- On Mac/Linux: run `chmod 400 your-key-file.key` first
- On Windows: right-click the `.key` file → Properties → Security → make sure only your user has access
- The username is `ubuntu` (not `root` or your Oracle username)

### Instance created but can't connect

**Problem:** The server's firewall might be blocking SSH.

**Solution:** 
1. Go to **Networking** → **Virtual Cloud Networks** → your VCN → **Security Lists** → Default Security List
2. Make sure there's an **Ingress Rule** for port 22 (SSH):
   - Source: `0.0.0.0/0`
   - Protocol: TCP
   - Destination Port: 22

---

## What's Next?

Once connected to your server, you can install Python and run any application:

```bash
# Update the system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3 python3-pip python3-venv -y

# Create a virtual environment
python3 -m venv ~/myapp
source ~/myapp/bin/activate

# Install your dependencies
pip install telethon  # (or whatever your app needs)
```

To keep your app running after you disconnect:

```bash
# Simple way: use screen
sudo apt install screen -y
screen -S myapp
python3 your_script.py
# Press Ctrl+A then D to detach (app keeps running)
# Reconnect later: screen -r myapp

# Better way: use systemd (auto-starts on reboot)
# See the app-specific setup guide for instructions
```

---

## Cost Summary

| Item | Cost |
|---|---|
| Oracle Cloud account | Free |
| VM.Standard.E2.1.Micro instance | Free (Always Free) |
| 46.6 GB storage | Free (up to 200 GB) |
| 10 TB/month outbound data | Free |
| Public IP address | Free |
| **Total monthly cost** | **$0** |

Oracle's Always Free resources **never expire**. From their FAQ: "Resources identified as Always Free will not be reclaimed. After your Free Trial expires, you'll continue to be able to use and manage your existing Always Free resources."

---

## For Technical Users

If you already have your own infrastructure, you don't need Oracle Cloud. The app runs anywhere with Python 3.8+:

- Your own VPS (DigitalOcean, Hetzner, Linode, AWS Lightsail — $4-5/month)
- Your home computer or Raspberry Pi
- Any Docker-capable server
- Your existing cloud VM

The Oracle Cloud guide above is specifically for non-technical users who want a free, zero-maintenance server without managing infrastructure.
