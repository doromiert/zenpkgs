{
  config,
  lib,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.services.zenfs.janitor;

  # Use the package from the overlay
  zenfsPackage = pkgs.zenfs-core;

  janitorConfig = pkgs.writeText "janitor_config.json" (
    builtins.toJSON {
      dumb = {
        grace_period = cfg.dumb.gracePeriod;
        watched_dirs = cfg.dumb.watchedDirs;
        rules = cfg.dumb.rules;
      };
      music = {
        music_dir = cfg.music.musicDir;
        unsafe_wipe = cfg.music.unsafeWipe;
      };
    }
  );
in
{
  options.services.zenfs.janitor = {
    enable = mkEnableOption "ZenFS Janitor Service";

    dumb = {
      enable = mkEnableOption "Dumb file sorter";
      gracePeriod = mkOption {
        type = types.int;
        default = 600;
      };
      watchedDirs = mkOption {
        type = types.listOf types.str;
        default = [ ];
      };
      rules = mkOption {
        type = types.attrs;
        default = { };
      };
    };

    music = {
      enable = mkEnableOption "Music library organizer";
      musicDir = mkOption {
        type = types.str;
        default = "/System/ZenFS/Audio";
      };
      unsafeWipe = mkOption {
        type = types.bool;
        default = false;
      };
    };
  };

  config = mkIf cfg.enable {
    # 1. Dumb Sorter Service
    systemd.services.zenfs-janitor-dumb = mkIf cfg.dumb.enable {
      description = "ZenFS Janitor (Dumb Sorter)";
      serviceConfig = {
        # Set PYTHONPATH to the root of the source so imports like 'from core import ...' work
        Environment = "PYTHONPATH=${zenfsPackage}/libexec/zenfs";

        # Call the specific script
        ExecStart = "${pkgs.python3}/bin/python3 ${zenfsPackage}/libexec/zenfs/janitor/dumb.py --config=${janitorConfig}";

        User = "root";
        Restart = "on-failure";
      };
    };

    # 2. Music Organizer Service
    systemd.services.zenfs-janitor-music = mkIf cfg.music.enable {
      description = "ZenFS Janitor (Music Organizer)";
      serviceConfig = {
        Environment = "PYTHONPATH=${zenfsPackage}/libexec/zenfs";
        ExecStart = "${pkgs.python3}/bin/python3 ${zenfsPackage}/libexec/zenfs/janitor/music.py --config=${janitorConfig}";
        User = "root";
      };
    };

    # 3. Timers
    systemd.timers.zenfs-janitor-dumb = mkIf cfg.dumb.enable {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "5m";
        OnUnitActiveSec = "10m";
      };
    };

    systemd.timers.zenfs-janitor-music = mkIf cfg.music.enable {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "10m";
        OnUnitActiveSec = "1h";
      };
    };
  };
}
