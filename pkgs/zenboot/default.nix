{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zenboot";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''

  '';

  meta = with lib; {
    description = "Bootloader and boot animation for ZenOS.";
    license = licenses.mit;
  };
}
