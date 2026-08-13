from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network

from fastapi import Request

from .config import AppSettings


IPAddress = IPv4Address | IPv6Address


def _parse_address(value: str) -> IPAddress | None:
    candidate = value.strip()
    if not candidate:
        return None
    # X-Forwarded-For carries bare addresses.  Brackets are accepted for a
    # normalized IPv6 value, but ports and obfuscated identifiers are rejected.
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    try:
        return ip_address(candidate)
    except ValueError:
        return None


class ClientAddressResolver:
    """Resolve a rate-limit/audit address without trusting arbitrary headers."""

    def resolve(self, request: Request, settings: AppSettings) -> str:
        direct_raw = request.client.host if request.client is not None else ""
        direct = _parse_address(direct_raw)
        if direct is None:
            return "unknown"

        trusted_networks = tuple(ip_network(value, strict=False) for value in settings.trusted_proxy_cidrs)
        if not any(direct in network for network in trusted_networks):
            return direct.compressed

        forwarded = request.headers.get("X-Forwarded-For", "")
        if not forwarded:
            return direct.compressed
        parts = [part.strip() for part in forwarded.split(",")]
        if len(forwarded) > 2048 or len(parts) > 32:
            return direct.compressed
        parsed = [_parse_address(part) for part in parts]
        if not parts or any(address is None for address in parsed):
            return direct.compressed

        # Walk from the directly connected proxy towards the client.  Only
        # explicitly trusted proxy hops may be skipped.
        chain = [address for address in parsed if address is not None] + [direct]
        candidate = direct
        for address in reversed(chain[:-1]):
            if not any(candidate in network for network in trusted_networks):
                break
            candidate = address
        return candidate.compressed


def get_client_address_resolver() -> ClientAddressResolver:
    return ClientAddressResolver()
