{
  lib,
  stdenv,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zenlink";
  version = "1.0.0";

  src = ./src;

  buildInputs = [ python3 ];

  installPhase = ''

  '';

  meta = with lib; {
    description = "Audio/Camera bridge between ZenOS and android.";
    license = licenses.mit;
  };
}
