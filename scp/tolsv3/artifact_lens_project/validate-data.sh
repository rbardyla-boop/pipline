#!/bin/bash
# Claude Master Data Validation Script
# Checks file integrity, detects corruption, validates YAML headers

MASTER_DIR="${HOME}/claude-master"
VALIDATION_LOG="${HOME}/.claude-archives/validation.log"
ERRORS=0

validate_claude_master() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting validation..." >> "$VALIDATION_LOG"
  
  # Check if master directory exists
  if [ ! -d "$MASTER_DIR" ]; then
    echo "❌ ERROR: Master directory not found: $MASTER_DIR" | tee -a "$VALIDATION_LOG"
    return 1
  fi
  
  # Check required markdown files
  echo "Checking required files..."
  required_files=("INSTRUCTIONS.md" "MEMORY.md" "HARDWARE.md" "PROJECTS.md" "CONTEXT.md")
  for file in "${required_files[@]}"; do
    if [ ! -f "$MASTER_DIR/$file" ]; then
      echo "❌ Missing: $file" | tee -a "$VALIDATION_LOG"
      ((ERRORS++))
    else
      # Check file size (warn if >50KB = likely corruption)
      size=$(stat -f%z "$MASTER_DIR/$file" 2>/dev/null || stat -c%s "$MASTER_DIR/$file" 2>/dev/null)
      lines=$(wc -l < "$MASTER_DIR/$file")
      
      if [ "$size" -gt 51200 ]; then
        echo "⚠️  WARNING: $file is large ($size bytes, $lines lines) - check for duplicates" | tee -a "$VALIDATION_LOG"
      else
        echo "✓ $file ($size bytes, $lines lines)" | tee -a "$VALIDATION_LOG"
      fi
      
      # Validate YAML headers
      if head -5 "$MASTER_DIR/$file" | grep -q "^---$"; then
        echo "  ✓ Valid YAML header" | tee -a "$VALIDATION_LOG"
      else
        echo "  ⚠️  Missing YAML header (optional but recommended)" | tee -a "$VALIDATION_LOG"
      fi
    fi
  done
  
  # Check git repository
  if [ -d "$MASTER_DIR/.git" ]; then
    commits=$(cd "$MASTER_DIR" && git rev-list --count HEAD 2>/dev/null)
    echo "✓ Git repo healthy ($commits commits)" | tee -a "$VALIDATION_LOG"
    
    # Check for uncommitted changes
    if [ -n "$(cd "$MASTER_DIR" && git status --porcelain 2>/dev/null)" ]; then
      echo "⚠️  Uncommitted changes detected" | tee -a "$VALIDATION_LOG"
      cd "$MASTER_DIR" && git status --short 2>/dev/null | tee -a "$VALIDATION_LOG"
    fi
  else
    echo "⚠️  WARNING: Git repository not initialized" | tee -a "$VALIDATION_LOG"
    ((ERRORS++))
  fi
  
  # Check archive backups
  if [ -d "$HOME/.claude-archives" ]; then
    backup_count=$(ls -d "$HOME/.claude-archives"/backup-* 2>/dev/null | wc -l)
    echo "✓ Backups available: $backup_count" | tee -a "$VALIDATION_LOG"
  else
    echo "⚠️  WARNING: Archive directory not found" | tee -a "$VALIDATION_LOG"
  fi
  
  # Check for duplicate content (entropy analysis)
  echo "Checking for duplicate entries..."
  for file in "$MASTER_DIR"/*.md; do
    filename=$(basename "$file")
    # Count lines that start with "- " (memory entries)
    entry_count=$(grep -c "^- " "$file" 2>/dev/null || echo "0")
    unique_count=$(grep "^- " "$file" 2>/dev/null | sort -u | wc -l)
    
    if [ "$entry_count" -gt 0 ]; then
      if [ "$entry_count" -ne "$unique_count" ]; then
        duplicates=$((entry_count - unique_count))
        echo "⚠️  $filename: $duplicates duplicate entries found" | tee -a "$VALIDATION_LOG"
        ((ERRORS++))
      fi
    fi
  done
  
  # Summary
  echo "" | tee -a "$VALIDATION_LOG"
  if [ $ERRORS -eq 0 ]; then
    echo "✅ Validation passed: All systems nominal" | tee -a "$VALIDATION_LOG"
    return 0
  else
    echo "❌ Validation failed: $ERRORS issue(s) found" | tee -a "$VALIDATION_LOG"
    echo "   Review: $VALIDATION_LOG"
    return 1
  fi
}

# Run validation
validate_claude_master

exit $?
