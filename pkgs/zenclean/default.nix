{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zenclean";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''

  '';

  meta = with lib; {
    description = "Automatic cleaning utility for ZenOS.";
    license = licenses.mit;
  };
}
