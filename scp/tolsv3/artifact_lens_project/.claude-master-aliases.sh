#!/bin/bash
# Claude Master CLI Aliases
# Add to ~/.bashrc or ~/.zshrc
# Source: source ~/.claude-master-aliases.sh

MASTER_DIR="${HOME}/claude-master"
ARCHIVE_DIR="${HOME}/.claude-archives"

# Update memory from CLI (faster than UI)
# Usage: claude-update-memory "TOLS frequency measured at 4.9 Hz, within target range"
alias claude-update-memory='_claude_update_memory() {
  entry="$(date +%Y-%m-%d\ %H:%M) | $1"
  echo -e "\n- $entry" >> "$MASTER_DIR/MEMORY.md"
  cd "$MASTER_DIR" && git add MEMORY.md && git commit -m "memory: $1" 2>/dev/null || true
}; _claude_update_memory'

# Add hardware note
# Usage: claude-hw-note "NE555 freq formula validated on breadboard"
alias claude-hw-note='_claude_hw_note() {
  entry="$(date +%Y-%m-%d\ %H:%M) | $1"
  echo -e "\n### $entry" >> "$MASTER_DIR/HARDWARE.md"
  cd "$MASTER_DIR" && git add HARDWARE.md && git commit -m "hardware: $1" 2>/dev/null || true
}; _claude_hw_note'

# Project status update
# Usage: claude-project-status "TOLS" "Frequency validation in progress, LED coupling visible"
alias claude-project-status='_claude_project_status() {
  project=$1
  status=$2
  sed -i "/### $project/,/^###/s/- \*\*Status\*\*:.*/- **Status**: $status/" "$MASTER_DIR/PROJECTS.md"
  cd "$MASTER_DIR" && git add PROJECTS.md && git commit -m "project: $project status updated" 2>/dev/null || true
}; _claude_project_status'

# Quick search memory
# Usage: claude-find "TOLS"
alias claude-find='_claude_find() {
  grep -r "$1" "$MASTER_DIR" --include="*.md" -n -A 2 -B 1 --color=always | head -30
}; _claude_find'

# View git log of changes
# Usage: claude-log (shows last 10 changes)
alias claude-log='cd "$MASTER_DIR" && git log --oneline -10'

# Backup and archive (automated versioning)
# Usage: claude-backup
alias claude-backup='_claude_backup() {
  timestamp=$(date +%Y-%m-%d_%H-%M-%S)
  backup_dir="$ARCHIVE_DIR/backup-$timestamp"
  mkdir -p "$backup_dir"
  cp -r "$MASTER_DIR"/* "$backup_dir/" 2>/dev/null || true
  cp "$MASTER_DIR/.git" "$backup_dir/.git" -r 2>/dev/null || true
  echo "✅ Backup created: $backup_dir"
  echo "📦 Total backups: $(ls -d $ARCHIVE_DIR/backup-* 2>/dev/null | wc -l)"
}; _claude_backup'

# Restore from backup
# Usage: claude-restore 2026-04-25_14-30-45
alias claude-restore='_claude_restore() {
  timestamp=$1
  backup_dir="$ARCHIVE_DIR/backup-$timestamp"
  if [ ! -d "$backup_dir" ]; then
    echo "❌ Backup not found: $backup_dir"
    echo "Available backups:"
    ls -d "$ARCHIVE_DIR"/backup-* 2>/dev/null | xargs basename -a
    return 1
  fi
  cp -r "$backup_dir"/* "$MASTER_DIR/"
  cd "$MASTER_DIR" && git add -A && git commit -m "restore: from backup $timestamp" 2>/dev/null || true
  echo "✅ Restored from: $backup_dir"
}; _claude_restore'

# View memory (pretty-printed)
# Usage: claude-memory
alias claude-memory='_claude_memory() {
  echo "📋 Current Memory State:"
  echo "========================"
  head -50 "$MASTER_DIR/MEMORY.md" | tail -45
  echo ""
  echo "(Showing first 45 lines. Full file: $MASTER_DIR/MEMORY.md)"
}; _claude_memory'

# Sync validation (checksum verification)
# Usage: claude-validate
alias claude-validate='_claude_validate() {
  echo "🔍 Validating memory integrity..."
  for file in "$MASTER_DIR"/*.md; do
    filename=$(basename "$file")
    size=$(wc -c < "$file")
    lines=$(wc -l < "$file")
    echo "✓ $filename: $size bytes, $lines lines"
  done
}; _claude_validate'

# Git status
# Usage: claude-status
alias claude-status='cd "$MASTER_DIR" && git status'

# Create new project context (template)
# Usage: claude-new-project "ProjectName" "Brief description"
alias claude-new-project='_claude_new_project() {
  project_name=$1
  description=$2
  cat >> "$MASTER_DIR/PROJECTS.md" << EOF

### $project_name
- **Status**: Initialized $(date +%Y-%m-%d)
- **Description**: $description
- **Next**: Define initial tasks
EOF
  cd "$MASTER_DIR" && git add PROJECTS.md && git commit -m "project: add $project_name" 2>/dev/null || true
  echo "✅ New project: $project_name"
}; _claude_new_project'

# Export to Obsidian format (future integration)
# Usage: claude-export-obsidian
alias claude-export-obsidian='_claude_export_obsidian() {
  export_dir="$HOME/obsidian-export-$(date +%Y%m%d)"
  mkdir -p "$export_dir"
  cp "$MASTER_DIR"/*.md "$export_dir/"
  echo "✅ Exported to: $export_dir"
}; _claude_export_obsidian'

# Master folder navigation
alias claude-cd='cd "$MASTER_DIR"'
alias claude-archive='ls -lah "$ARCHIVE_DIR"'

echo "✅ Claude Master CLI aliases loaded"
echo "Available commands:"
echo "  claude-update-memory <note>    - Add to MEMORY.md"
echo "  claude-hw-note <note>          - Add to HARDWARE.md"
echo "  claude-project-status <proj> <status> - Update project status"
echo "  claude-find <keyword>          - Search all .md files"
echo "  claude-log                     - View git history"
echo "  claude-backup                  - Create versioned backup"
echo "  claude-restore <timestamp>     - Restore from backup"
echo "  claude-memory                  - View current memory"
echo "  claude-validate                - Check file integrity"
echo "  claude-status                  - Git status"
echo "  claude-new-project <name> <desc> - Create project context"
echo "  claude-cd                      - Navigate to master folder"
