{ pkgs ? import <nixpkgs> {} }:

let
  orggle = pkgs.callPackage ./orggle.nix {};
in
{
  inherit orggle;

  # For development environment
  orggleDevShell = pkgs.mkShell {
    buildInputs = with pkgs; [
      python3
      python3.pkgs.pytest
      python3.pkgs.pyyaml
      python3.pkgs.black
      python3.pkgs.flake8
    ];

    shellHook = ''
      echo "orggle development environment"
      echo "Run 'orggle --version' to test"
    '';
  };
}
