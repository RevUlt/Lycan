# Backup & Migration Guide

This document covers how to back up Lycan's critical data and restore it on a new machine.

---

## Critical Files

| Path | Contents | Sensitivity |
|------|----------|-------------|
| `.env.docker` | Tokens and API keys | 🔴 **High — never share** |
| `data/chroma_db/` | Lycan memory embeddings | 🟡 Medium |
| PostgreSQL dump | `social_feeds`, bot config | 🟡 Medium |

---

## Quick Backup

```bash
# 1. Create backup directory
mkdir -p ~/lycan-backup

# 2. Copy environment file (SENSITIVE — do not share or upload publicly)
cp /path/to/Lycan/.env.docker ~/lycan-backup/

# 3. Export database
sudo docker exec lycan-db pg_dump -U lycan lycan > ~/lycan-backup/database.sql

# 4. Copy ChromaDB memory
sudo docker cp lycan-bot:/app/data/chroma_db ~/lycan-backup/

# 5. Compress
tar -czvf ~/lycan-backup-$(date +%Y%m%d).tar.gz ~/lycan-backup/

# 6. Upload to Google Drive (manually or via rclone)
```

> ⚠️ The `.env.docker` file contains secrets. Store the backup in an encrypted location (e.g., Google Drive with 2FA, or an encrypted volume). Never commit it to version control.

---

## Restore on a New Machine

```bash
# 1. Clone the repository
git clone https://github.com/RevUlt/Lycan.git
cd Lycan

# 2. Extract backup archive
tar -xzvf lycan-backup-YYYYMMDD.tar.gz

# 3. Restore environment file
cp lycan-backup/.env.docker .

# 4. Start containers
sudo docker compose up -d

# 5. Restore database
cat lycan-backup/database.sql | sudo docker exec -i lycan-db psql -U lycan lycan

# 6. Restore memory embeddings
sudo docker cp lycan-backup/chroma_db lycan-bot:/app/data/

# 7. Restart bot
sudo docker compose restart lycan

# 8. Re-subscribe EventSub webhooks (requires Cloudflare Tunnel to be configured first)
curl -X POST https://<your-domain>/admin/subscribe-all
```

---

## Cloudflare Tunnel

After migrating, update the tunnel routing:

1. Go to **Cloudflare Zero Trust → Access → Tunnels**
2. Edit the existing tunnel or create a new one
3. Point `socials.<your-domain>` → `localhost:6100`

---

## Automated Backup (Optional)

Add a cron job to run backups daily:

```bash
# Run at 3:00 AM every day
0 3 * * * /path/to/lycan-backup.sh >> /var/log/lycan-backup.log 2>&1
```

Make sure the script has execute permissions:
```bash
chmod +x /path/to/lycan-backup.sh
```
