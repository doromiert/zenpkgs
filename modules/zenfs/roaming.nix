# Formerly modules/roaming.nix
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.zenos.roaming;
in
{
  options.zenos.roaming = {
    enable = mkEnableOption "ZenOS Roaming Profiles";
    persistPath = mkOption {
      type = types.str;
      default = "/nix/persist";
    };
  };

  config = mkIf cfg.enable {
    environment.persistence."${cfg.persistPath}" = {
      hideMounts = true;
      directories = [
        "/etc/nixos"
        "/var/log"
        "/var/lib/bluetooth"
        "/var/lib/nixos"
        "/var/lib/systemd/coredump"
        "/etc/NetworkManager/system-connections"

        # ZenFS Configs
        "/System/ZenFS/Database"
      ];
      files = [
        "/etc/machine-id"
        "/etc/ssh/ssh_host_ed25519_key"
        "/etc/ssh/ssh_host_ed25519_key.pub"
        "/etc/ssh/ssh_host_rsa_key"
        "/etc/ssh/ssh_host_rsa_key.pub"
      ];
    };
  };
}
