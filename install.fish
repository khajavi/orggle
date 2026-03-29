#!/usr/bin/env fish
# orggle Installation Script for fish shell

set -l GREEN '\033[0;32m'
set -l BLUE '\033[0;34m'
set -l YELLOW '\033[1;33m'
set -l RED '\033[0;31m'
set -l NC '\033[0m'

echo -e "$BLUE=== orggle Installation ===$NC\n"

# Check Python version
echo -e "$BLUE""Checking Python version...$NC"
if not command -v python3 &> /dev/null
    echo -e "$RED""Error: python3 is not installed$NC"
    exit 1
end

set PYTHON_VERSION (python3 --version | string split ' ')[2]
echo -e "$GREEN""✓ Found Python $PYTHON_VERSION$NC\n"

# Check curl
echo -e "$BLUE""Checking curl...$NC"
if not command -v curl &> /dev/null
    echo -e "$RED""Error: curl is not installed$NC"
    exit 1
end
echo -e "$GREEN""✓ Found curl$NC\n"

# Get installation directory
set -l INSTALL_DIR (test -n "$argv[1]"; and echo $argv[1]; or echo ".")
if not test -d "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
end

echo -e "$BLUE""Installation directory: $INSTALL_DIR$NC\n"

# Create virtual environment
echo -e "$BLUE""Creating Python virtual environment...$NC"
python3 -m venv "$INSTALL_DIR/.venv"
source "$INSTALL_DIR/.venv/bin/activate.fish"
echo -e "$GREEN""✓ Virtual environment created$NC\n"

# Upgrade pip
echo -e "$BLUE""Upgrading pip...$NC"
pip install --quiet --upgrade pip
echo -e "$GREEN""✓ pip upgraded$NC\n"

# Install dependencies
echo -e "$BLUE""Installing dependencies...$NC"
if test -f "$INSTALL_DIR/requirements.txt"
    pip install --quiet -r "$INSTALL_DIR/requirements.txt" 2>/dev/null; or echo -e "$YELLOW""⚠ Warning: Some dependencies failed to install (this is OK if running without YAML support)$NC"
end
echo -e "$GREEN""✓ Dependencies installed$NC\n"

# Set API token
echo -e "$BLUE""Configuration:$NC"
if test -z "$TOGGL_API_TOKEN"
    echo -e "$YELLOW""⚠ TOGGL_API_TOKEN environment variable not set$NC"
    echo -e "   $BLUE""Set it with:$NC set -gx TOGGL_API_TOKEN 'your_api_token'"
else
    echo -e "$GREEN""✓ TOGGL_API_TOKEN is set$NC"
end

echo ""

# Create wrapper script
set -l WRAPPER "$INSTALL_DIR/orggle"
cat > "$WRAPPER" << 'EOFWRAPPER'
#!/usr/bin/env fish
set SCRIPT_DIR (dirname (status filename))
source "$SCRIPT_DIR/.venv/bin/activate.fish"
python3 "$SCRIPT_DIR/orggle.py" $argv
EOFWRAPPER

chmod +x "$WRAPPER"
echo -e "$GREEN""✓ Created wrapper script: $WRAPPER$NC\n"

# Summary
echo -e "$BLUE""=== Installation Complete ===$NC\n"
echo -e "Usage:"
echo -e "  $GREEN""$WRAPPER <org_file>$NC"
echo -e "  $GREEN""$WRAPPER <org_file> --batch daily$NC"
echo -e "  $GREEN""$WRAPPER <org_file> --day 2026-03-28$NC\n"

echo -e "Before first use:"
echo -e "  1. $BLUE""Set API token:$NC"
echo -e "     set -gx TOGGL_API_TOKEN 'your_api_token'"
echo -e "  2. $BLUE""(Optional) Edit config.yaml for custom mappings$NC"
echo -e "  3. $BLUE""Run the script:$NC"
echo -e "     $WRAPPER your-org-file.org\n"

deactivate
echo -e "$GREEN""Ready to use!$NC"
