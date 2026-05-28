#!/usr/bin/env markdown
# Claude Master (Layer 2.5) - Linux Setup Guide

**10% Improvements Over Standard Layer 2:**
1. ✅ **Git versioning** (replaces manual archives, auditable, diff-able)
2. ✅ **CLI-first aliases** (faster updates than UI)
3. ✅ **Automated backups** (cron or systemd timer)
4. ✅ **Data validation** (corruption detection)
5. ✅ **Fuzzy search** (fzf integration for fast memory lookup)
6. ✅ **YAML headers** (structured data, enables parsing)
7. ✅ **Cross-file linking** (markdown links between projects)
8. ✅ **Archive management** (automatic retention policy)
9. ✅ **Git history** (full audit trail, revert any change)
10. ✅ **Template system** (new project scaffold)

---

## Installation (One-Time, ~5 minutes)

### Step 1: Clone/Download Build Files
```bash
git clone <repo-url> ~/claude-master-setup
cd ~/claude-master-setup
```

Or if you're reading this, files are already in `/home/claude/claude-master-build/`.

### Step 2: Run Initialization
```bash
bash init-claude-master.sh
```

This creates:
- `~/claude-master/` (main directory)
- `~/.claude-archives/` (backup storage)
- 5 markdown files with your frameworks
- Git repository initialized

### Step 3: Install CLI Aliases
Add to your shell RC file (`~/.bashrc`, `~/.zshrc`, or `~/.fish/config.fish`):
```bash
source ~/.claude-master-aliases.sh
```

Then reload:
```bash
source ~/.bashrc  # or zshrc, etc.
```

### Step 4: Set Up Automated Backups
```bash
bash install-backup-automation.sh
```

Choose:
- **Option 1**: Cron (simple, no extra config)
- **Option 2**: Systemd timer (modern, integrated)

### Step 5: Optional—Enable Fuzzy Search
Install fzf:
```bash
# Ubuntu/Debian
sudo apt-get install fzf

# macOS
brew install fzf

# Or build from source: https://github.com/junegunn/fzf
```

Then add to your aliases:
```bash
alias claude-fzf='bash ~/.claude-master-setup/fzf-search.sh'
```

### Step 6: Validate System
```bash
bash validate-data.sh
```

Expected output:
```
✓ INSTRUCTIONS.md (...)
✓ MEMORY.md (...)
✓ HARDWARE.md (...)
✓ PROJECTS.md (...)
✓ CONTEXT.md (...)
✓ Git repo healthy (1 commits)
✓ Backups available: 0
✅ Validation passed: All systems nominal
```

---

## Daily Usage

### Update Memory (Fastest Way)
```bash
# From terminal, mid-session
claude-update-memory "TOLS frequency validated at 4.9 Hz, LED coupling visible"

# This automatically:
# 1. Appends to ~/claude-master/MEMORY.md
# 2. Commits to git with timestamp
# 3. Creates auditable history
```

### Add Hardware Notes
```bash
claude-hw-note "NE555 astable mode frequency formula verified on breadboard"
```

### Update Project Status
```bash
claude-project-status "TOLS" "Breadboard prototype iteration 2, frequency validation in progress"
```

### Quick Search
```bash
# Search keyword in all .md files
claude-find "oscillator"

# Interactive fuzzy search (requires fzf)
claude-fzf --interactive

# Search and open in editor
claude-fzf-edit "TOLS"

# Browse projects
claude-fzf --projects
```

### View Git History
```bash
# Last 10 changes
claude-log

# Full status
claude-status

# Specific file diff
cd ~/claude-master && git diff MEMORY.md
```

### Manual Backup
```bash
claude-backup
# Creates: ~/.claude-archives/backup-2026-04-25_14-30-45/
```

### Restore from Backup
```bash
# List available backups
ls ~/.claude-archives/

# Restore specific backup
claude-restore 2026-04-25_14-30-45
```

### Validate Data Integrity
```bash
bash validate-data.sh
# Checks for:
# - Missing files
# - File corruption (size anomalies)
# - Duplicate entries
# - Valid YAML headers
# - Git repository health
```

### Export to Obsidian (Future Integration)
```bash
claude-export-obsidian
# Creates: ~/obsidian-export-20260425/
```

---

## File Structure

```
~/claude-master/
├── .git/                    # Git repository (version control)
├── INSTRUCTIONS.md          # VAL/APEX/KLEON rules, voice guidelines
├── MEMORY.md               # Running state, active projects, preferences
├── HARDWARE.md             # TOLS specs, NE555 pinouts, EEG design
├── PROJECTS.md             # All active projects with status
└── CONTEXT.md              # Personal/business context, frameworks

~/.claude-archives/
├── backup-2026-04-25_14-30-45/  # Weekly automated backups
├── backup-2026-04-18_14-30-45/
├── backup.log                    # Backup history
└── validation.log                # Validation audit trail
```

---

## Advanced: Custom Workflows

### Create New Project
```bash
claude-new-project "Fenix EEG Integration" "Build custom EEG sensor pipeline for Fenix RSD detection"
```

### Add Custom Alias
Edit `~/.claude-master-aliases.sh` and add:
```bash
alias claude-my-command='_claude_my_command() {
  # Your script here
}; _claude_my_command'
```

### Manual Git Operations
```bash
cd ~/claude-master

# View full log with diffs
git log -p MEMORY.md

# See what changed between backups
git diff HEAD~5 MEMORY.md

# Revert specific file to last commit
git checkout HEAD MEMORY.md

# Create named version (important milestone)
git tag -a "TOLS-v0.2-breadboard-validation" -m "First oscillation confirmed"
git tag -l  # List all tags
```

---

## 10% Improvements Explained

| Feature | Layer 2 Standard | Layer 2.5 Enhanced | Win |
|---------|-----------------|-------------------|-----|
| **Versioning** | Manual copies | Git (auditable, diff-able) | 5 min/week → 30 sec/week |
| **Updates** | UI-based | CLI aliases | Copy-paste speed |
| **Backups** | Manual weekly | Automated (cron/systemd) | Set once, runs forever |
| **Search** | grep (slow) | fzf fuzzy (interactive) | 3 sec → 0.3 sec |
| **Structure** | Flat .md files | YAML headers + links | Parseable, queryable |
| **Integrity** | Manual audits | Automated validation | Catch corruption early |
| **Scalability** | Single folder | Git history + archives | Unlimited growth |
| **Recovery** | File backups | Git + timestamped archives | Granular, instant restore |

---

## Troubleshooting

### Aliases Not Working
```bash
# Check if sourced
echo $MASTER_DIR

# If empty, source manually
source ~/.claude-master-aliases.sh

# Or verify it's in your rc file
grep claude-master-aliases ~/.bashrc
```

### Backup Not Running
```bash
# Check cron status
crontab -l | grep claude

# Check systemd timer status
systemctl --user status claude-backup.timer
systemctl --user list-timers

# Manual backup (test)
bash ~/.claude-backup.sh
```

### Git Errors
```bash
# Check git status
cd ~/claude-master && git status

# Reset to last clean state
git reset --hard HEAD

# If corrupted, restore from backup
claude-restore BACKUP_TIMESTAMP
```

### Missing Files After Update
```bash
# Check what happened
git log --oneline MEMORY.md | head -5

# Restore file from specific commit
git show COMMIT_HASH:MEMORY.md > MEMORY.md

# Or restore entire backup
claude-restore BACKUP_TIMESTAMP
```

---

## Integration with Claude (Web/App)

### Attach Master Folder
1. Open Claude in web or app
2. In chat, click "Attach files"
3. Select `~/claude-master/`
4. Claude can now read all .md files in context

### Sync Workflow
1. Work in Claude conversation
2. Say: "Update MEMORY.md with: [discovery]"
3. Claude updates the file
4. Or update manually: `claude-update-memory "..."`
5. Commit is automatic

### Use in Claude Code
When using Claude Code (terminal), the master folder is accessible:
```bash
# Claude Code can read and write to files
cat ~/claude-master/MEMORY.md
echo "- New discovery" >> ~/claude-master/MEMORY.md
```

---

## Maintenance Schedule

| Frequency | Task | Time |
|-----------|------|------|
| **Per session** | Run `claude-update-memory` for discoveries | 30 sec |
| **Weekly** | Auto-backup runs (set once) | 0 sec (automated) |
| **Weekly** | Review `MEMORY.md` for accuracy | 5 min |
| **Monthly** | Validate data integrity | 2 min |
| **Quarterly** | Archive old backups (>90 days auto-deleted) | 0 sec (automated) |
| **As needed** | Search memory with `claude-fzf` | 5-10 sec |

---

## Quick Reference

```bash
# Memory updates
claude-update-memory "note"
claude-hw-note "hardware discovery"
claude-project-status "PROJECT" "status"

# Search
claude-find "keyword"
claude-fzf --interactive
claude-fzf-edit "keyword"

# Backups & git
claude-backup
claude-restore TIMESTAMP
claude-log
claude-status

# Maintenance
claude-validate
claude-memory (view first 45 lines)
claude-archive (list backups)

# Navigation
claude-cd (go to master folder)
```

---

## Next Steps

1. **Complete one update** using `claude-update-memory` to test
2. **Verify backup** runs this week
3. **Use `claude-find`** to search your own memory
4. **Attach to Claude** and start syncing discoveries
5. **Review weekly** to keep memory clean and current

---

**Version**: Layer 2.5 v1.0 (2026-04-25)
**Maintenance**: Ryan Bardyla (@clovelearni0)
**Framework**: VAL + APEX + KLEON
