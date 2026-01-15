{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "view";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''
    echo "this package isn't ready yet. remove it from your config"
  '';

  meta = with lib; {
    description = "Image viewer and gallery for ZenOS.";
    license = licenses.mit;
  };
}
