#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== orggle Uninstallation ===${NC}\n"

# Get installation directory
INSTALL_DIR="${1:-.}"
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Error: Installation directory not found: $INSTALL_DIR${NC}"
    exit 1
fi

echo -e "${BLUE}Installation directory: $INSTALL_DIR${NC}\n"

# Check if .venv exists
if [ -d "$INSTALL_DIR/.venv" ]; then
    echo -e "${YELLOW}Found virtual environment at $INSTALL_DIR/.venv${NC}"
    read -p "Remove virtual environment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR/.venv"
        echo -e "${GREEN}✓ Virtual environment removed${NC}\n"
    fi
fi

# Check if wrapper script exists
if [ -f "$INSTALL_DIR/orggle" ]; then
    echo -e "${YELLOW}Found wrapper script at $INSTALL_DIR/orggle${NC}"
    read -p "Remove wrapper script? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$INSTALL_DIR/orggle"
        echo -e "${GREEN}✓ Wrapper script removed${NC}\n"
    fi
fi

# Check if database exists
DB_PATH=~/.orggle.db
if [ -f "$DB_PATH" ]; then
    echo -e "${YELLOW}Found database at $DB_PATH${NC}"
    read -p "Remove database? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$DB_PATH"
        echo -e "${GREEN}✓ Database removed${NC}\n"
    fi
fi

# Check if fish completions exist
if [ -f ~/.config/fish/completions/orggle.fish ]; then
    echo -e "${YELLOW}Found fish completions at ~/.config/fish/completions/orggle.fish${NC}"
    read -p "Remove fish completions? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f ~/.config/fish/completions/orggle.fish
        echo -e "${GREEN}✓ Fish completions removed${NC}\n"
    fi
fi

echo -e "${BLUE}=== Uninstallation Complete ===${NC}\n"
echo -e "${GREEN}orggle has been uninstalled.${NC}"
