# Formerly modules/zenfs.nix
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.zenos.fs;
in
{
  options.zenos.fs = {
    enable = mkEnableOption "ZenFS Standard Directory Structure";
  };

  config = mkIf cfg.enable {
    systemd.tmpfiles.rules = [
      "d /System 0755 root root -"
      "d /System/ZenFS 0777 root root -"
      "d /System/ZenFS/Audio 0777 root root -"
      "d /System/ZenFS/Audio/Music 0777 root root -"
      "d /System/ZenFS/Audio/Samples 0777 root root -"
      "d /System/ZenFS/Audio/Recordings 0777 root root -"
      "d /System/ZenFS/Documents 0777 root root -"
      "d /System/ZenFS/Documents/Financial 0700 root root -"
      "d /System/ZenFS/Images 0777 root root -"
      "d /System/ZenFS/Images/Screenshots 0777 root root -"
      "d /System/ZenFS/Downloads 0777 root root -"
      "d /System/ZenFS/Database 0777 root root -"

      # Symlink compatibility for standard XDG folders if needed
      # "L+ /home/user/Music - - - - /System/ZenFS/Audio/Music"
    ];
  };
}
