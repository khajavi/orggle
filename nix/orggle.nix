{ lib
, stdenv
, fetchFromGitHub
, python3
, pyyaml
, makeWrapper
}:

let
  pname = "orggle";
  version = "0.1.0";
  src = fetchFromGitHub {
    owner = "khajavi";
    repo = "orggle";
    rev = "v${version}";
    sha256 = "sha256-K1ZQ3R2i0fYwvK2T3W7T3W7T3W7T3W7T3W7T3W7T3W7T3W7T3W7T3W7U=";
  };
in
stdenv.mkDerivation rec {
  inherit pname version src;

  nativeBuildInputs = [ makeWrapper ];

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
      --prefix PYTHONPATH : "${pyyaml}/lib/python${python3.version}/site-packages"
  '';

  meta = with lib; {
    description = "Sync org-mode clock entries to Toggl Track";
    longDescription = ''
      orggle is a CLI tool that synchronizes org-mode clock entries to Toggl Track.
      
      Features:
      - Multi-profile support for multiple Toggl accounts
      - Environment variable substitution for secure token storage
      - Batch mode for daily syncing
      - Per-profile configuration
      - Fish shell completions
    '';
    homepage = "https://github.com/khajavi/orggle";
    license = licenses.mit;
    maintainers = [ ];
    platforms = platforms.unix;
    mainProgram = "orggle";
  };
}
