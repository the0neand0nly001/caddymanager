#!/bin/bash
# Deterministic answers for the isolated native-install smoke test.
case "$2" in
    "Caddy Manager Setup") exit 1 ;;
    "Base Domains") echo "home.lab, services.test" >&2 ;;
    "AdGuard IP") echo "192.0.2.53" >&2 ;;
    "Admin Username") echo "native-test-owner" >&2 ;;
    "Admin Password") echo "test'quoted-password" >&2 ;;
    "Discord Webhook") exit 1 ;;
    "Ready to Install") exit 0 ;;
    *) echo "Unexpected setup prompt" >&2; exit 2 ;;
esac
