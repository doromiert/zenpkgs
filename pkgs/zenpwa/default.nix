{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zenpwa";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''

  '';

  meta = with lib; {
    description = "Progressive Web Apps based on firefox for ZenOS services.";
    license = licenses.mit;
  };
}
