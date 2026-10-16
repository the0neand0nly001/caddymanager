"""Base-domain validation and persistent defaults for new routes."""

import ipaddress
import re

from .config import CONFIG_LOCK, load_config, save_config

TLS_MODES = {
    "internal": "Internal HTTPS",
    "auto": "Automatic HTTPS",
    "http": "HTTP only",
}


def configured_domains(settings):
    return settings.get("DOMAINS", [settings.get("DOMAIN", "home.lab")])


def domain_tls_mode(settings, domain):
    mode = settings.get("DOMAIN_TLS", {}).get(domain, "internal")
    return mode if mode in TLS_MODES else "internal"


def normalize_domain(value):
    value = value.strip().lower()
    if value.endswith("."):
        value = value[:-1]
    try:
        value = value.encode("idna").decode("ascii")
        ipaddress.ip_address(value)
    except UnicodeError:
        raise ValueError("Enter a valid base domain, such as home.lab.") from None
    except ValueError:
        pass
    else:
        raise ValueError("Enter a domain name, not an IP address.")
    labels = value.split(".")
    if (
        len(value) > 253
        or len(labels) < 2
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in labels
        )
    ):
        raise ValueError("Enter a valid base domain without a protocol, port or path.")
    return value


def change_domain(action, value, tls_mode="internal"):
    domain = normalize_domain(value)
    if action not in {"add_domain", "update_domain", "remove_domain"}:
        raise ValueError("Invalid base-domain action.")
    if action != "remove_domain" and tls_mode not in TLS_MODES:
        raise ValueError("Choose a valid TLS mode.")

    with CONFIG_LOCK:
        settings = load_config()
        domains = list(configured_domains(settings))
        existing = next(
            (name for name in domains if name.lower().rstrip(".") == domain), None
        )
        modes = dict(settings.get("DOMAIN_TLS", {}))
        if action == "add_domain":
            if existing is not None:
                raise ValueError(f"Base domain {domain} already exists.")
            domains.append(domain)
            modes[domain] = tls_mode
        else:
            if existing is None:
                raise ValueError("That base domain is no longer configured.")
            if action == "remove_domain":
                domains.remove(existing)
                modes.pop(existing, None)
            else:
                modes[existing] = tls_mode
        settings["DOMAINS"] = domains
        settings["DOMAIN_TLS"] = modes
        save_config(settings)
    return domain
