#!/bin/bash
# Claude Master Layer 2.5 - Copy-Paste Execution Guide
# Copy each section and run in your terminal

# ============================================================================
# STEP 1: Initialize system (one-time, ~2 minutes)
# ============================================================================

# Download and navigate to build directory (or use the one provided)
cd /home/claude/claude-master-build

# Run init script
bash init-claude-master.sh

# Expected output:
# ✅ Created: /home/YOUR_USER/claude-master
# ✅ Git initialized (version control active)


# ============================================================================
# STEP 2: Install CLI aliases (add to ~/.bashrc or ~/.zshrc)
# ============================================================================

# Option A: Copy aliases file to home directory
cp /home/claude/claude-master-build/.claude-master-aliases.sh ~/.claude-master-aliases.sh

# Option B: Add to ~/.bashrc or ~/.zshrc
echo "" >> ~/.bashrc
echo "# Claude Master aliases" >> ~/.bashrc
echo "source ~/.claude-master-aliases.sh" >> ~/.bashrc

# Reload shell
source ~/.bashrc


# ============================================================================
# STEP 3: Test aliases
# ============================================================================

# Verify aliases are loaded
claude-cd

# You should be in ~/claude-master/
# If not, run: source ~/.bashrc (and check if it's installed)


# ============================================================================
# STEP 4: Set up automated backups (choose one method)
# ============================================================================

# METHOD 1: Cron (simple, runs every Sunday 2 AM)
crontab -l 2>/dev/null | grep -v "claude-backup" > /tmp/crontab.tmp || true
echo "0 2 * * 0 bash /home/claude/claude-master-build/backup-script.sh" >> /tmp/crontab.tmp
crontab /tmp/crontab.tmp
rm /tmp/crontab.tmp

# Verify cron installed
crontab -l | grep claude-backup


# ============================================================================
# STEP 5: Optional - Install fzf for fuzzy search
# ============================================================================

# Ubuntu/Debian
sudo apt-get install -y fzf

# macOS
brew install fzf

# Verify
fzf --version


# ============================================================================
# STEP 6: Validate system
# ============================================================================

bash /home/claude/claude-master-build/validate-data.sh

# Expected: ✅ Validation passed: All systems nominal


# ============================================================================
# STEP 7: First update (test the system works)
# ============================================================================

# Try updating memory from CLI
claude-update-memory "System initialized, Layer 2.5 active, git versioning enabled"

# Check it was saved
cat ~/claude-master/MEMORY.md | tail -5

# Check git logged it
cd ~/claude-master && git log --oneline | head -3


# ============================================================================
# DONE! You're ready to use Claude Master
# ============================================================================

# Quick reference:
# 
# Daily:
#   claude-update-memory "discovery"
#   claude-hw-note "hardware finding"
#   claude-find "search term"
#
# Weekly:
#   claude-backup (manual, or automatic via cron)
#   Review ~/claude-master/MEMORY.md
#
# Whenever:
#   claude-fzf --interactive (search everything)
#   claude-log (view git history)
#   claude-cd (navigate to master folder)
#
# Attach ~/claude-master/ to Claude and start syncing!

echo "✅ Claude Master Layer 2.5 ready to use"
