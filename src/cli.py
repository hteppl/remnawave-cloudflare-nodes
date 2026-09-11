import os
import signal

import questionary
from questionary import Choice, Separator


def _load_config():
    from .config import Config
    return Config()


def _load_hosts_config():
    from .hosts_config import HostsConfig
    return HostsConfig()


def _print_separator():
    print("─" * 48)


def action_show():
    try:
        config = _load_config()
    except Exception as e:
        print(f"✗  {e}")
        return

    from .utils.dns import build_fqdn
    zones = config.get_all_zones()

    api_info = f" ({config.api_host}:{config.api_port})" if config.api_enabled else ""
    tg_info = f" (language={config.language})" if config.telegram_enabled else ""

    _print_separator()
    print("  Service")
    print(f"    Check interval : {config.check_interval}s")
    print(f"    Log level      : {config.log_level}")
    print(f"    API            : {'enabled' + api_info if config.api_enabled else 'disabled'}")
    print(f"    Telegram       : {'enabled' + tg_info if config.telegram_enabled else 'disabled'}")

    print("\n  Domains & Zones")
    if not zones:
        print("    (no zones configured)")
    else:
        for z in zones:
            fqdn = build_fqdn(z["name"], z["domain"])
            print(f"    {fqdn}  ttl={z['ttl']}  proxied={z['proxied']}")
            for entry in z["nodes"]:
                note = f"  →  {entry['address']}" if entry["address"] != entry["ip"] else ""
                print(f"      {entry['ip']}{note}")

    hosts_config = _load_hosts_config()
    print("\n  Managed Hosts")
    if not hosts_config.enabled:
        print("    (no hosts.yml — all matching hosts are managed)")
    else:
        for entry in hosts_config.entries:
            uuid = entry.get("uuid", "")
            label = entry.get("label", "")
            label_str = f"  {label}" if label else ""
            print(f"    {uuid}{label_str}")

    _print_separator()


def action_validate():
    try:
        config = _load_config()
        config.validate()
    except Exception as e:
        _print_separator()
        print(f"  ✗  Config invalid: {e}")
        _print_separator()
        return

    from .utils.dns import build_fqdn
    zones = config.get_all_zones()
    hosts_config = _load_hosts_config()

    _print_separator()
    print("  ✓  Config is valid\n")
    print(f"    Check interval : {config.check_interval}s")
    print(f"    Log level      : {config.log_level}")
    print(f"    Domains        : {len(config.domains)}")
    print(f"    Zones          : {len(zones)}")
    for z in zones:
        fqdn = build_fqdn(z["name"], z["domain"])
        print(f"      {fqdn}  —  {len(z['nodes'])} node(s), ttl={z['ttl']}, proxied={z['proxied']}")
    if hosts_config.enabled:
        print(f"\n    Managed hosts  : {len(hosts_config.uuids)}")
        for entry in hosts_config.entries:
            uuid = entry.get("uuid", "")
            label = entry.get("label", "")
            label_str = f" ({label})" if label else ""
            print(f"      {uuid}{label_str}")
    _print_separator()


def action_reload():
    try:
        os.kill(1, signal.SIGHUP)
        _print_separator()
        print("  ✓  Reload signal sent — check container logs for result")
        _print_separator()
    except ProcessLookupError:
        _print_separator()
        print("  ✗  Process 1 not found")
        _print_separator()
    except PermissionError:
        _print_separator()
        print("  ✗  Permission denied")
        _print_separator()


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
        action = questionary.select(
            "Select action:",
            choices=CHOICES,
            use_shortcuts=False,
        ).ask()

        if action is None or action == "exit":
            break

        print()
        ACTIONS[action]()
        print()


if __name__ == "__main__":
    main()
