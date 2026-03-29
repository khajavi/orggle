{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "orggle-dev";

  buildInputs = with pkgs; [
    python3
    python3.pkgs.pytest
    python3.pkgs.pyyaml
    python3.pkgs.black
    python3.pkgs.flake8
    fish
  ];

  shellHook = ''
    echo "═══════════════════════════════════════════════════════════"
    echo "  orggle development environment"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Available commands:"
    echo "  python orggle.py --version   Test orggle"
    echo "  python orggle.py --help       Show help"
    echo "  pytest                        Run tests"
    echo "  black .                       Format code"
    echo "  flake8 .                     Lint code"
    echo ""
    echo "Environment variables to set:"
    echo "  export TOGGL_API_TOKEN='your_token'"
    echo ""
  '';
}
