{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "monitor";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''
    echo "this package isn't ready yet. remove it from your config"
  '';

  meta = with lib; {
    description = "Overview/admin panel for ZenOS-specific services.";
    license = licenses.mit;
  };
}
