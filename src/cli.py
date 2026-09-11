import os
import signal

import questionary
from questionary import Choice, Separator

from .config import Config
from .hosts_config import HostsConfig


def _print_separator():
    print("─" * 48)


def _print_boxed(*lines: str) -> None:
    _print_separator()
    for line in lines:
        print(line)
    _print_separator()


def _print_managed_hosts(hosts_config: HostsConfig, indent: str, label_format: str) -> None:
    for entry in hosts_config.entries:
        label = entry.get("label", "")
        print(f"{indent}{entry.get('uuid', '')}{label_format.format(label) if label else ''}")


def action_show():
    try:
        config = Config()
    except Exception as e:
        print(f"✗  {e}")
        return

    zones = config.get_all_zones()
    api = f"enabled ({config.api_host}:{config.api_port})" if config.api_enabled else "disabled"
    telegram = f"enabled (language={config.language})" if config.telegram_enabled else "disabled"

    _print_separator()
    print("  Service")
    print(f"    Check interval : {config.check_interval}s")
    print(f"    Log level      : {config.log_level}")
    print(f"    API            : {api}")
    print(f"    Telegram       : {telegram}")

    print("\n  Domains & Zones")
    if not zones:
        print("    (no zones configured)")
    for z in zones:
        print(f"    {z.fqdn}  ttl={z.ttl}  proxied={z.proxied}")
        for entry in z.nodes:
            note = f"  →  {entry.address}" if entry.address != entry.ip else ""
            print(f"      {entry.ip}{note}")

    hosts_config = HostsConfig()
    print("\n  Managed Hosts")
    if not hosts_config.enabled:
        print("    (no hosts.yml — all matching hosts are managed)")
    else:
        _print_managed_hosts(hosts_config, " " * 4, "  {}")

    _print_separator()


def action_validate():
    try:
        config = Config()
        config.validate()
    except Exception as e:
        _print_boxed(f"  ✗  Config invalid: {e}")
        return

    zones = config.get_all_zones()
    hosts_config = HostsConfig()

    _print_separator()
    print("  ✓  Config is valid\n")
    print(f"    Check interval : {config.check_interval}s")
    print(f"    Log level      : {config.log_level}")
    print(f"    Domains        : {len(config.domains)}")
    print(f"    Zones          : {len(zones)}")
    for z in zones:
        print(f"      {z.fqdn}  —  {len(z.nodes)} node(s), ttl={z.ttl}, proxied={z.proxied}")
    if hosts_config.enabled:
        print(f"\n    Managed hosts  : {len(hosts_config.uuids)}")
        _print_managed_hosts(hosts_config, " " * 6, " ({})")
    _print_separator()


def action_reload():
    try:
        os.kill(1, signal.SIGHUP)
        _print_boxed("  ✓  Reload signal sent — check container logs for result")
    except ProcessLookupError:
        _print_boxed("  ✗  Process 1 not found")
    except PermissionError:
        _print_boxed("  ✗  Permission denied")


ACTIONS = {
    "show": action_show,
    "validate": action_validate,
    "reload": action_reload,
}

CHOICES = [
    Choice("Show config", value="show"),
    Choice("Validate config", value="validate"),
    Choice("Reload config (hot)", value="reload"),
    Separator(),
    Choice("Exit", value="exit"),
]


def main():
    print("\n  remnawave-cloudflare-nodes\n")

    while True:
        action = questionary.select("Select action:", choices=CHOICES, use_shortcuts=False).ask()
        if action is None or action == "exit":
            break

        print()
        ACTIONS[action]()
        print()


if __name__ == "__main__":
    main()
