#!/usr/bin/env fish
# orggle Uninstallation Script for fish shell

set -l GREEN '\033[0;32m'
set -l BLUE '\033[0;34m'
set -l YELLOW '\033[1;33m'
set -l RED '\033[0;31m'
set -l NC '\033[0m'

echo -e "$BLUE=== orggle Uninstallation ===$NC\n"

# Get installation directory
set -l INSTALL_DIR (test -n "$argv[1]"; and echo $argv[1]; or echo ".")
if not test -d "$INSTALL_DIR"
    echo -e "$RED""Error: Installation directory not found: $INSTALL_DIR$NC"
    exit 1
end

echo -e "$BLUE""Installation directory: $INSTALL_DIR$NC\n"

# Check if .venv exists
if test -d "$INSTALL_DIR/.venv"
    echo -e "$YELLOW""Found virtual environment at $INSTALL_DIR/.venv$NC"
    read -l -P "Remove virtual environment? (y/n) " response
    if test "$response" = "y" -o "$response" = "Y"
        rm -rf "$INSTALL_DIR/.venv"
        echo -e "$GREEN""✓ Virtual environment removed$NC\n"
    end
end

# Check if wrapper script exists
if test -f "$INSTALL_DIR/orggle"
    echo -e "$YELLOW""Found wrapper script at $INSTALL_DIR/orggle$NC"
    read -l -P "Remove wrapper script? (y/n) " response
    if test "$response" = "y" -o "$response" = "Y"
        rm -f "$INSTALL_DIR/orggle"
        echo -e "$GREEN""✓ Wrapper script removed$NC\n"
    end
end

# Check if database exists
set -l DB_PATH ~/.orggle.db
if test -f "$DB_PATH"
    echo -e "$YELLOW""Found database at $DB_PATH$NC"
    read -l -P "Remove database? (y/n) " response
    if test "$response" = "y" -o "$response" = "Y"
        rm -f "$DB_PATH"
        echo -e "$GREEN""✓ Database removed$NC\n"
    end
end

# Check if fish completions exist
if test -f ~/.config/fish/completions/orggle.fish
    echo -e "$YELLOW""Found fish completions at ~/.config/fish/completions/orggle.fish$NC"
    read -l -P "Remove fish completions? (y/n) " response
    if test "$response" = "y" -o "$response" = "Y"
        rm -f ~/.config/fish/completions/orggle.fish
        echo -e "$GREEN""✓ Fish completions removed$NC\n"
    end
end

echo -e "$BLUE""=== Uninstallation Complete ===$NC\n"
echo -e "$GREEN""orggle has been uninstalled.$NC"
