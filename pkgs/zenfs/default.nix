{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zenfs-core";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''
    mkdir -p $out/libexec/zenfs
    cp -r * $out/libexec/zenfs/
    chmod +x $out/libexec/zenfs/main.py

    # Optional: Create a binary wrapper if you want to run it manually
    mkdir -p $out/bin
    ln -s $out/libexec/zenfs/main.py $out/bin/zenfs-janitor
  '';

  meta = with lib; {
    description = "ZenFS Core Scripts and Janitor";
    license = licenses.mit;
  };
}
