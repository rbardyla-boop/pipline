#!/bin/bash
# Claude Master Backup Automation Setup
# Choose your method: cron (simple) or systemd timer (modern)

BACKUP_SCRIPT="$HOME/.claude-backup.sh"
MASTER_DIR="${HOME}/claude-master"

echo "Choose backup automation method:"
echo "1) Cron (simple, runs every Sunday 2 AM)"
echo "2) Systemd Timer (modern, integrates with OS)"
echo ""
read -p "Enter choice (1 or 2): " choice

case $choice in
  1)
    echo "Setting up Cron backup..."
    
    # Copy backup script to home
    cp backup-script.sh "$BACKUP_SCRIPT"
    chmod +x "$BACKUP_SCRIPT"
    
    # Add to crontab
    crontab -l 2>/dev/null | grep -v "claude-backup" > /tmp/crontab.tmp || true
    echo "0 2 * * 0 $BACKUP_SCRIPT" >> /tmp/crontab.tmp
    crontab /tmp/crontab.tmp
    rm /tmp/crontab.tmp
    
    echo "✅ Cron backup installed"
    echo "Runs every Sunday at 2:00 AM"
    echo "View logs: tail -f ~/.claude-archives/backup.log"
    ;;
    
  2)
    echo "Setting up Systemd Timer backup..."
    
    # Copy backup script
    mkdir -p ~/.local/bin
    cp backup-script.sh ~/.local/bin/claude-backup
    chmod +x ~/.local/bin/claude-backup
    
    # Create systemd service
    mkdir -p ~/.config/systemd/user
    cat > ~/.config/systemd/user/claude-backup.service << EOF
[Unit]
Description=Claude Master Weekly Backup
After=network.target

[Service]
Type=oneshot
ExecStart=%h/.local/bin/claude-backup
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Create systemd timer
    cat > ~/.config/systemd/user/claude-backup.timer << EOF
[Unit]
Description=Claude Master Weekly Backup Timer
Requires=claude-backup.service

[Timer]
OnCalendar=Sun *-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable and start timer
    systemctl --user daemon-reload
    systemctl --user enable claude-backup.timer
    systemctl --user start claude-backup.timer
    
    echo "✅ Systemd timer backup installed"
    echo "Runs every Sunday at 2:00 AM"
    echo "View status: systemctl --user status claude-backup.timer"
    echo "View logs: journalctl --user -u claude-backup.service -f"
    ;;
    
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac

echo ""
echo "Manual backup anytime: claude-backup"
echo "Restore from backup: claude-restore TIMESTAMP"
