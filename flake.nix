{
  description = "Sync org-mode clock entries to Toggl Track";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        orggle = pkgs.stdenv.mkDerivation {
          pname = "orggle";
          version = "0.1.1";

          src = self;

          nativeBuildInputs = [ pkgs.makeWrapper ];

          installPhase = ''
            mkdir -p $out/bin
            mkdir -p $out/etc/fish/completions
            mkdir -p $out/share/fish/vendor_completions.d

            cp orggle.py $out/bin/orggle
            chmod +x $out/bin/orggle

            if [ -f completions.fish ]; then
              cp completions.fish $out/etc/fish/completions/orggle.fish
              cp completions.fish $out/share/fish/vendor_completions.d/orggle.fish
            fi

            wrapProgram $out/bin/orggle \
              --prefix PYTHONPATH : "${pkgs.python3.pkgs.pyyaml}/lib/python${pkgs.python3.version}/site-packages"
          '';

          meta = with pkgs.lib; {
            description = "Sync org-mode clock entries to Toggl Track";
            homepage = "https://github.com/khajavi/orggle";
            license = licenses.mit;
            platforms = platforms.unix;
            mainProgram = "orggle";
          };
        };
      in
      {
        packages = {
          orggle = orggle;
          default = orggle;
        };

        apps = {
          orggle = {
            type = "app";
            program = "${orggle}/bin/orggle";
          };
          default = self.apps.${system}.orggle;
        };

        devShells.default = pkgs.mkShell {
          name = "orggle-dev";
          packages = with pkgs; [
            python3
            python3.pkgs.pytest
            python3.pkgs.pyyaml
            python3.pkgs.black
            python3.pkgs.flake8
            fish
          ];
        };
      }
    );
}
