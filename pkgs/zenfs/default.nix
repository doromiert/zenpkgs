{
  lib,
  stdenv,
  python3,
  makeWrapper,
  ...
}:

let
  # python environment with all dependencies required by the scripts
  pythonEnv = python3.withPackages (ps: [
    ps.watchdog
    ps.pyyaml
    ps.pillow
    ps.mutagen
    ps.psutil
  ]);
in
stdenv.mkDerivation {
  pname = "zenfs";
  version = "1.0.0";

  # Expects scripts to be in pkgs/zenfs/src
  src = ./src;

  nativeBuildInputs = [ makeWrapper ];
  buildInputs = [ pythonEnv ];

  installPhase = ''
    runHook preInstall

    # 1. Install the raw source scripts to libexec
    mkdir -p $out/libexec/zenfs
    cp -r ./* $out/libexec/zenfs/

    # 2. Create the bin directory
    mkdir -p $out/bin

    # 3. Helper function to wrap scripts
    # Usage: wrapScript <internal_path> <binary_name>
    wrapScript() {
      makeWrapper ${pythonEnv}/bin/python3 $out/bin/$2 \
        --add-flags "$out/libexec/zenfs/$1" \
        --prefix PYTHONPATH : "$out/libexec/zenfs/core:$out/libexec/zenfs/user"
    }

    # 4. Generate Binaries
    wrapScript "janitor/dumb.py" "zenfs-janitor-dumb"
    wrapScript "janitor/music.py" "zenfs-janitor-music"
    wrapScript "janitor/ml.py" "zenfs-janitor-ml"
    wrapScript "core/offloader.py" "zenfs-offloader"
    wrapScript "core/mounting.py" "zenfs-gatekeeper"
    wrapScript "core/indexer.py" "zenfs-indexer"
    wrapScript "core/roaming.py" "zenfs-roaming"
    wrapScript "user/mint.py" "zenfs-mint"

    runHook postInstall
  '';

  meta = with lib; {
    description = "ZenFS Core Scripts and Janitor Suite";
    license = licenses.mit;
    platforms = platforms.linux;
  };
}
