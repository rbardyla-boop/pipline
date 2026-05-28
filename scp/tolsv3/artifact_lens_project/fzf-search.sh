#!/bin/bash
# Claude Master Fuzzy Search (fzf integration)
# Requires: fzf (install: apt-get install fzf or brew install fzf)
# Usage: claude-fzf (interactive) or claude-search "keyword"

MASTER_DIR="${HOME}/claude-master"

# Check if fzf is installed
if ! command -v fzf &> /dev/null; then
  echo "fzf not found. Install with:"
  echo "  Ubuntu/Debian: sudo apt-get install fzf"
  echo "  macOS: brew install fzf"
  echo "  Other: https://github.com/junegunn/fzf"
  exit 1
fi

# Interactive fuzzy search (opens file in editor)
claude_fzf_interactive() {
  selected=$(grep -r "." "$MASTER_DIR"/*.md --line-number -H | \
    fzf \
      --preview "echo {} | cut -d: -f1-2 | xargs -I {} sed -n '{}p' $MASTER_DIR/*.md" \
      --preview-window=right:50% \
      --height 60% \
      --multi \
      --bind "ctrl-a:select-all" \
      --bind "ctrl-d:deselect-all" \
      --bind "ctrl-e:execute(echo {} | cut -d: -f1 | xargs -r \$EDITOR)" \
      --header "Fuzzy search Claude Master memory (Ctrl-E to edit)"
  )
  
  if [ -n "$selected" ]; then
    echo "$selected" | while read line; do
      file=$(echo "$line" | cut -d: -f1)
      linenum=$(echo "$line" | cut -d: -f2)
      echo "→ $file:$linenum"
    done
  fi
}

# Quick keyword search (returns matching lines)
claude_fzf_search() {
  keyword="$1"
  if [ -z "$keyword" ]; then
    echo "Usage: claude-search 'keyword' or source this script then: claude_fzf_search 'keyword'"
    return 1
  fi
  
  grep -r "$keyword" "$MASTER_DIR"/*.md --line-number -H --color=always | \
    fzf \
      --preview "echo {} | cut -d: -f1-2 | xargs -I {} sed -n '{}p' $MASTER_DIR/*.md" \
      --preview-window=right:50% \
      --height 40%
}

# Search and open in editor
claude_fzf_edit() {
  keyword="$1"
  
  file=$(grep -r "$keyword" "$MASTER_DIR"/*.md --line-number -H | \
    fzf \
      --preview "echo {} | cut -d: -f1-2 | xargs -I {} sed -n '{}p' $MASTER_DIR/*.md" \
      --preview-window=right:50% \
      --height 40% | \
    cut -d: -f1 | \
    head -1
  )
  
  if [ -n "$file" ]; then
    ${EDITOR:-vim} "$file"
  fi
}

# Fuzzy search project names
claude_fzf_projects() {
  project=$(grep "^### " "$MASTER_DIR/PROJECTS.md" | sed 's/^### //' | \
    fzf \
      --preview "grep -A 10 'Projects' $MASTER_DIR/PROJECTS.md | grep -A 5 '{}'" \
      --height 20%
  )
  
  if [ -n "$project" ]; then
    echo "Selected: $project"
    grep -A 5 "### $project" "$MASTER_DIR/PROJECTS.md"
  fi
}

# Main function (called when sourced as alias)
if [ "$1" = "--interactive" ]; then
  claude_fzf_interactive
elif [ "$1" = "--projects" ]; then
  claude_fzf_projects
elif [ -n "$1" ]; then
  claude_fzf_search "$1"
else
  echo "Claude Master Fuzzy Search"
  echo "Usage:"
  echo "  claude-fzf --interactive          Search all memory interactively"
  echo "  claude-fzf <keyword>              Quick search by keyword"
  echo "  claude-fzf-edit <keyword>         Search and open in editor"
  echo "  claude-fzf --projects             Browse projects"
  echo ""
  echo "Requires: fzf (https://github.com/junegunn/fzf)"
fi
