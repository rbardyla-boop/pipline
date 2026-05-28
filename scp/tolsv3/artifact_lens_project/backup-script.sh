#!/bin/bash
# Claude Master Auto-Backup Script
# Runs weekly, creates timestamped backups with git history
# Install: crontab -e and add entry below

MASTER_DIR="${HOME}/claude-master"
ARCHIVE_DIR="${HOME}/.claude-archives"
RETENTION_DAYS=90

backup_claude_master() {
  timestamp=$(date +%Y-%m-%d_%H-%M-%S)
  backup_dir="$ARCHIVE_DIR/backup-$timestamp"
  
  # Create backup directory
  mkdir -p "$backup_dir"
  
  # Copy markdown files
  cp "$MASTER_DIR"/*.md "$backup_dir/" 2>/dev/null || {
    echo "[$(date)] ERROR: Failed to copy markdown files" >> "$ARCHIVE_DIR/backup.log"
    return 1
  }
  
  # Copy git history
  if [ -d "$MASTER_DIR/.git" ]; then
    cp -r "$MASTER_DIR/.git" "$backup_dir/.git" 2>/dev/null || true
  fi
  
  # Create metadata file
  cat > "$backup_dir/BACKUP_INFO" << EOF
Created: $(date)
Backup Type: Automatic Weekly
Files: $(ls -1 "$MASTER_DIR"/*.md 2>/dev/null | wc -l) markdown files
Git Commits: $(cd "$MASTER_DIR" && git rev-list --count HEAD 2>/dev/null || echo "0")
Size: $(du -sh "$MASTER_DIR" 2>/dev/null | cut -f1)
Retention: Keep for $RETENTION_DAYS days
EOF

  # Log backup
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Backup created: $backup_dir" >> "$ARCHIVE_DIR/backup.log"
  
  # Clean old backups (older than RETENTION_DAYS)
  find "$ARCHIVE_DIR" -maxdepth 1 -type d -name "backup-*" -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null
  
  # Optional: Send to cloud backup if available
  # Uncomment if using rsync/rclone to cloud storage
  # rsync -az "$backup_dir" remote:/backups/claude/ 2>/dev/null || true
  
  return 0
}

# Execute backup
backup_claude_master

# Exit with status
exit $?
