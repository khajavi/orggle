#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== orggle Installation ===${NC}\n"

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓ Found Python $PYTHON_VERSION${NC}\n"

# Check curl
echo -e "${BLUE}Checking curl...${NC}"
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Found curl${NC}\n"

# Get installation directory
INSTALL_DIR="${1:-.}"
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
fi

echo -e "${BLUE}Installation directory: $INSTALL_DIR${NC}\n"

# Create virtual environment
echo -e "${BLUE}Creating Python virtual environment...${NC}"
python3 -m venv "$INSTALL_DIR/.venv"
source "$INSTALL_DIR/.venv/bin/activate"
echo -e "${GREEN}✓ Virtual environment created${NC}\n"

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --quiet --upgrade pip
echo -e "${GREEN}✓ pip upgraded${NC}\n"

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    pip install --quiet -r "$INSTALL_DIR/requirements.txt" || echo -e "${YELLOW}⚠ Warning: Some dependencies failed to install (this is OK if running without YAML support)${NC}"
fi
echo -e "${GREEN}✓ Dependencies installed${NC}\n"

# Create config directory
echo -e "${BLUE}Setting up config directory...${NC}"
mkdir -p ~/.config/orggle
echo -e "${GREEN}✓ Config directory created at ~/.config/orggle${NC}\n"

# Create default config if it doesn't exist
if [ ! -f ~/.config/orggle/config.yaml ]; then
    echo -e "${BLUE}Creating default configuration...${NC}"
    cat > ~/.config/orggle/config.yaml << 'EOFCONFIG'
# orggle configuration - Multiple profile support

# Default profile to use if --profile flag not specified
default_profile: default

# Global default tag (can be overridden per profile)
tag: orggle

# Define profiles here
profiles:
  default:
    # API token can use ${ENV_VAR} syntax for environment variable substitution
    api_token: ${TOGGL_API_TOKEN}
    # tag: orggle  # Optional: override global tag
    default_project: Documentation
    org_mappings:
      - pattern: "^\\s*- rest$"
        description: "Break Time"
EOFCONFIG
    echo -e "${GREEN}✓ Created default config at ~/.config/orggle/config.yaml${NC}\n"
fi

# Set API token
echo -e "${BLUE}Configuration:${NC}"
if [ -z "${TOGGL_API_TOKEN:-}" ]; then
    echo -e "${YELLOW}⚠ TOGGL_API_TOKEN environment variable not set${NC}"
    echo -e "   ${BLUE}Set it with:${NC} export TOGGL_API_TOKEN='your_api_token'"
else
    echo -e "${GREEN}✓ TOGGL_API_TOKEN is set${NC}"
fi

echo ""

# Create wrapper script
WRAPPER="$INSTALL_DIR/orggle"
cat > "$WRAPPER" << 'EOF'
#!/bin/bash
# Get absolute path to the script's directory
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
source "$SCRIPT_DIR/.venv/bin/activate"
python3 "$SCRIPT_DIR/orggle.py" "$@"
EOF

chmod +x "$WRAPPER"
echo -e "${GREEN}✓ Created wrapper script: $WRAPPER${NC}\n"

# Install fish completions
echo -e "${BLUE}Installing fish shell completions...${NC}"
mkdir -p ~/.config/fish/completions
if [ -f "$INSTALL_DIR/completions.fish" ]; then
    cp "$INSTALL_DIR/completions.fish" ~/.config/fish/completions/orggle.fish
    echo -e "${GREEN}✓ Fish completions installed at ~/.config/fish/completions/orggle.fish${NC}\n"
else
    echo -e "${YELLOW}⚠ Warning: completions.fish not found (completions not installed)${NC}\n"
fi

# Summary
echo -e "${BLUE}=== Installation Complete ===${NC}\n"
echo -e "Usage:"
echo -e "  ${GREEN}$WRAPPER <org_file>${NC}"
echo -e "  ${GREEN}$WRAPPER <org_file> --profile work${NC}"
echo -e "  ${GREEN}$WRAPPER <org_file> --batch daily${NC}\n"

echo -e "Before first use:"
echo -e "  1. ${BLUE}Set API token:${NC}"
echo -e "     export TOGGL_API_TOKEN='your_api_token'"
echo -e "  2. ${BLUE}(Optional) Edit config at ~/.config/orggle/config.yaml to add more profiles${NC}"
echo -e "  3. ${BLUE}Run the script:${NC}"
echo -e "     $WRAPPER your-org-file.org\n"

deactivate
echo -e "${GREEN}Ready to use!${NC}"
