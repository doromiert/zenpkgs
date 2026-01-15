{
  description = "ZenPKGS - Custom Package Overlay for ZenOS";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      # 1. The Overlay
      overlays.default = import ./overlay.nix;

      # 2. Standalone Packages (Dynamic)
      # This allows 'nix build .#package-name' to work automatically
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ self.overlays.default ];
            config.allowUnfree = true;
          };

          # We check the overlay keys to know what to export,
          # ensuring we only export our custom packages, not all of nixpkgs.
          overlayOutput = self.overlays.default pkgs pkgs;
        in
        # Filter the full pkgs set to only include things defined in our overlay
        nixpkgs.lib.filterAttrs (n: v: builtins.hasAttr n overlayOutput) pkgs
      );
    };
}
