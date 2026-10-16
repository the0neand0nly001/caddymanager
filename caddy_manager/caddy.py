"""Caddyfile access, route parsing and block formatting."""

import re
import subprocess

from .config import load_config
from .backend import uses_admin_api


def read_caddyfile(caddyfile_path):
    """Helper to read Caddyfile safely via sudo to avoid permission blocks"""
    try:
        if uses_admin_api():
            with open(caddyfile_path, encoding="utf-8") as file:
                return file.read()
        res = subprocess.run(
            ["sudo", "cat", caddyfile_path], capture_output=True, text=True, check=True
        )
        return res.stdout
    except Exception:
        return ""


def write_caddyfile(caddyfile_path, content):
    """Helper to write Caddyfile safely via sudo"""
    try:
        if uses_admin_api():
            with open(caddyfile_path, "w", encoding="utf-8") as file:
                file.write(content)
            return True
        process = subprocess.Popen(
            ["sudo", "tee", caddyfile_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        process.communicate(input=content)
        return process.returncode == 0
    except Exception:
        return False


def append_caddyfile(caddyfile_path, block):
    """Helper to append block to Caddyfile via sudo"""
    try:
        if uses_admin_api():
            with open(caddyfile_path, "a", encoding="utf-8") as file:
                file.write(block)
            return True
        process = subprocess.Popen(
            ["sudo", "tee", "-a", caddyfile_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        process.communicate(input=block)
        return process.returncode == 0
    except Exception:
        return False


def get_routes():
    config = load_config()
    caddyfile_path = config.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile")
    content = read_caddyfile(caddyfile_path)
    return parse_routes(content)


def parse_routes(content):
    """Read proxy targets and return unique routes sorted by domain."""
    if not content:
        return []
    try:
        routes = []
        pattern = r"^\s*([a-zA-Z0-9][-a-zA-Z0-9._/:]+)\s*\{"

        for match in re.finditer(pattern, content, re.MULTILINE):
            domain_raw = match.group(1).strip()
            domain = re.sub(r"^https?://", "", domain_raw)

            if domain in ["{", "}", "admin", "http", "tls", "transport"]:
                continue

            start_idx = match.end()

            brace_count = 1
            end_idx = start_idx
            while end_idx < len(content) and brace_count > 0:
                if content[end_idx] == "{":
                    brace_count += 1
                elif content[end_idx] == "}":
                    brace_count -= 1
                end_idx += 1

            block = content[start_idx:end_idx]

            target = "Unknown"
            proxy_match = re.search(
                r"reverse_proxy\s+(?:https?://|http://)?([^\s\{]+)", block
            )
            if proxy_match:
                target = proxy_match.group(1)

            if not any(r["domain"] == domain for r in routes):
                routes.append({"domain": domain, "target": target})

        return sorted(routes, key=lambda x: x["domain"])
    except Exception:
        return []


def build_route_block(subdomain, ip_str, port_str, protocol, tls_mode="internal"):
    """Format frontend TLS independently of the selected backend protocol."""
    if tls_mode not in {"internal", "auto", "http"}:
        raise ValueError("Invalid TLS mode")
    if protocol == "https":
        proxy = (
            f"    reverse_proxy {protocol}://{ip_str}:{port_str} {{\n"
            "        transport http {\n"
            "            tls_insecure_skip_verify\n"
            "        }\n"
            "    }\n"
        )
    else:
        proxy = f"    reverse_proxy {protocol}://{ip_str}:{port_str}\n"
    address = f"http://{subdomain}" if tls_mode == "http" else subdomain
    tls = "    tls internal\n" if tls_mode == "internal" else ""
    return f"\n{address} {{\n{proxy}{tls}}}\n"


def remove_route_block(content, target_route):
    """Remove the matched block; nested blocks retain the existing limitation."""
    pattern = r"(?:http://)?" + re.escape(target_route) + r"\s*\{[^}]*\}"
    new_content = re.sub(pattern, "", content, flags=re.DOTALL)
    return re.sub(r"\n\s*\n\s*\n", "\n\n", new_content)
