{
  lib,
  stdenv,
  fontforge,
  python3,
  ...
}:

stdenv.mkDerivation {
  pname = "zero";
  version = "1.0.0";

  src = ./src;

  # Define paths for the builder to use
  rawPath = ./resources/zero-src;

  condensedPath =
    if builtins.pathExists ./resources/zero-raw-condensed then ./resources/zero-raw-condensed else "";

  nativeBuildInputs = [
    fontforge
    python3
  ];

  buildPhase = ''
    runHook preBuild

    # 1. Prepare the build script
    cp $src/make-zero.py ./build.py

    # 2. [PATH FIX] Create the output structure locally first.
    # The script expects 'share/fonts/truetype' to exist.
    mkdir -p share/fonts/truetype

    echo "Generating Zero font..."

    # [FIX] We pass out=. ONLY to this command environment.
    # This prevents overwriting the global $out variable (which points to /nix/store/...)
    # so the installPhase can still find the correct destination.
    out=. fontforge -script ./build.py

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    # Create the actual destination directory in the Nix store
    mkdir -p $out/share/fonts/truetype

    # Install the generated files from our local build folder to the store
    install -Dm644 share/fonts/truetype/*.ttf -t $out/share/fonts/truetype/

    runHook postInstall
  '';

  meta = with lib; {
    description = "The Zero font, a minimalist display font.";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
