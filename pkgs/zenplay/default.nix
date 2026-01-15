{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zenplay";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''
    echo "this package isn't ready yet. remove it from your config"
  '';

  meta = with lib; {
    description = "Automatic emulator library manager for ZenOS.";
    license = licenses.mit;
  };
}
