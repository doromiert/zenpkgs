{
  lib,
  stdenv,
  fontforge,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zero"; # Renamed to just "zero" as requested
  version = "1.0.0";

  src = ./src;

  # Define paths for the builder to use
  # We assume resources are adjacent to this file (matching your snippet structure)
  rawPath = ./resources/zero-src;

  # Conditional path logic adapted for mkDerivation
  condensedPath =
    if builtins.pathExists ./resources/zero-raw-condensed then ./resources/zero-raw-condensed else "";

  nativeBuildInputs = [
    fontforge
    python3
  ];

  buildPhase = ''
    runHook preBuild

    # Prepare the build script from the source directory
    # Assumes make-zero.py is inside the ./src folder
    cp $src/make-zero.py ./build.py

    echo "Generating Zero font..."
    # Execute the python script via FontForge. 
    # The script should read the 'rawPath' and 'condensedPath' env vars defined above.
    fontforge -script ./build.py

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/fonts/truetype

    # Install generated TTFs
    install -Dm644 *.ttf -t $out/share/fonts/truetype/

    runHook postInstall
  '';

  meta = with lib; {
    description = "The Zero font, a minimalist display font.";
    license = licenses.mit;
    platforms = platforms.all;
    maintainers = with maintainers; [ "doromiert" ];
  };
}
