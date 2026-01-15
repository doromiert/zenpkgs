final: prev:

let
  lib = prev.lib;
  packagesDir = ./pkgs;

  # 1. Read the ./pkgs directory
  dirContents = builtins.readDir packagesDir;

  # 2. Filter: Only accept directories
  # We assume every directory here is a package containing a 'main.nix'
  isPackageDir = name: type: type == "directory";
  packageDirs = lib.filterAttrs isPackageDir dirContents;

  # 3. Map names to final.callPackage pointing to main.nix
  # Result: { zenfs = final.callPackage ./pkgs/zenfs/main.nix {}; }
  autoPackages = lib.mapAttrs (
    name: _: final.callPackage (packagesDir + "/${name}/main.nix") { }
  ) packageDirs;

in
autoPackages
