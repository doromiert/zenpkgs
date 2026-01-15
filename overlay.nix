final: prev:

let
  lib = prev.lib;
  packagesDir = ./pkgs;

  # 1. Read the ./pkgs directory
  dirContents = builtins.readDir packagesDir;

  # 2. Filter: Only accept directories (containing default.nix) or .nix files
  # This ignores READMEs, .gitkeeps, etc.
  isValidPackage =
    name: type: (type == "directory") || (type == "regular" && lib.hasSuffix ".nix" name);

  packageNames = lib.filterAttrs isValidPackage dirContents;

  # 3. Map names to final.callPackage
  # This creates { zenos-hello = final.callPackage ./pkgs/zenos-hello {}; ... }
  autoPackages = lib.mapAttrs (
    name: _: final.callPackage (packagesDir + "/${name}") { }
  ) packageNames;

in
# Merge auto-discovered packages with any manual overrides you might want
autoPackages
// {
  # You can still add manual overrides for nixpkgs here if needed
  # discord = prev.discord.override { ... };
}
