#!/usr/bin/env python3
"""
BeamMP Radmin VPN Helper (Free OSS Lite Edition)
Zero-dependency Python 3 utility for private BeamMP servers over Radmin VPN.

Features:
  - Automatically detects local Radmin VPN IPv4 address (26.x.x.x)
  - Checks UDP & TCP availability of BeamMP port 30814 (with Windows PID hint if busy)
  - Generates a clean, ready-to-use ServerConfig.toml for private Radmin VPN hosting
  - Built-in --self-test suite

License: MIT
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_PORT = 30814
DEFAULT_MAP = "/levels/west_coast_usa/info.json"

KNOWN_MAPS: dict[str, str] = {
    "west_coast_usa": "/levels/west_coast_usa/info.json",
    "east_coast_usa": "/levels/east_coast_usa/info.json",
    "italy": "/levels/italy/info.json",
    "utah": "/levels/utah/info.json",
    "gridmap_v2": "/levels/gridmap_v2/info.json",
    "johnson_valley": "/levels/johnson_valley/info.json",
    "jungle_rock_island": "/levels/jungle_rock_island/info.json",
    "hirochi_raceway": "/levels/hirochi_raceway/info.json",
    "automation_test_track": "/levels/automation_test_track/info.json",
    "small_island": "/levels/small_island/info.json",
    "derby": "/levels/derby/info.json",
    "industrial": "/levels/industrial/info.json",
}

RADMIN_NETWORK = ipaddress.IPv4Network("26.0.0.0/8")


def _configure_stdio_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except OSError:
                pass


def is_radmin_ip(ip_str: str) -> bool:
    """Return True if ip_str is a valid IPv4 address inside Radmin VPN's 26.0.0.0/8 range."""
    try:
        addr = ipaddress.IPv4Address(ip_str.strip())
        return addr in RADMIN_NETWORK
    except ValueError:
        return False


def extract_radmin_ips_from_text(output: str) -> list[dict[str, str]]:
    """
    Parse `ipconfig`, `ip addr`, or `ifconfig` text output and return candidate
    Radmin VPN 26.x.x.x IPv4 entries ordered by confidence (adapter name match first).
    """
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    current_adapter = "Unknown Adapter"

    # Match common Windows ipconfig / Linux ip addr adapter headers
    adapter_header_re = re.compile(
        r"^(?:[A-Za-z0-9_.\-/ ]+adapter\s+([^:]+):|\d+:\s+([^:@]+)[@:].*|<[^>]+>)",
        re.IGNORECASE,
    )
    ipv4_re = re.compile(r"\b(26\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Windows ipconfig section header usually has zero leading whitespace and ends with ':'
        if not raw_line.startswith((" ", "\t")) and raw_line.rstrip().endswith(":"):
            current_adapter = raw_line.rstrip().rstrip(":").strip()
        else:
            m_hdr = adapter_header_re.match(line)
            if m_hdr:
                hdr = m_hdr.group(1) or m_hdr.group(2)
                if hdr:
                    current_adapter = hdr.strip()

        for match in ipv4_re.finditer(line):
            candidate = match.group(1)
            # Skip subnet mask or broadcast if obvious (e.g. 26.255.255.255)
            if candidate in seen or not is_radmin_ip(candidate):
                continue
            if candidate.endswith(".0") or candidate.endswith(".255"):
                continue
            seen.add(candidate)
            is_radmin_adapter = "radmin" in current_adapter.lower()
            results.append(
                {
                    "ip": candidate,
                    "adapter": current_adapter,
                    "confidence": "high" if is_radmin_adapter else "medium",
                }
            )

    results.sort(key=lambda item: (0 if item["confidence"] == "high" else 1, item["ip"]))
    return results


def detect_radmin_ips() -> list[dict[str, str]]:
    """Detect local Radmin VPN IPv4 addresses (26.x.x.x) using zero external packages."""
    found: list[dict[str, str]] = []
    seen_ips: set[str] = set()

    def _add(entries: list[dict[str, str]]) -> None:
        for entry in entries:
            if entry["ip"] not in seen_ips:
                seen_ips.add(entry["ip"])
                found.append(entry)

    system = platform.system().lower()
    commands: list[list[str]] = []
    if system == "windows":
        commands.append(["ipconfig"])
    else:
        commands.append(["ip", "-4", "addr"])
        commands.append(["ifconfig"])

    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
                check=False,
            )
            if proc.stdout:
                _add(extract_radmin_ips_from_text(proc.stdout))
        except (OSError, subprocess.SubprocessError):
            continue

    # Fallback via socket.getaddrinfo on hostname
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if is_radmin_ip(ip) and ip not in seen_ips:
                seen_ips.add(ip)
                found.append(
                    {
                        "ip": ip,
                        "adapter": "Hostname/Socket",
                        "confidence": "medium",
                    }
                )
    except OSError:
        pass

    found.sort(key=lambda item: (0 if item["confidence"] == "high" else 1, item["ip"]))
    return found


def _find_port_owner_windows(port: int) -> str | None:
    """Return brief PID / process info holding the port on Windows if available."""
    if platform.system().lower() != "windows":
        return None
    try:
        proc = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
            check=False,
        )
        pattern = re.compile(rf"^\s*(TCP|UDP)\s+\S+:{port}\b.*?(\d+)\s*$", re.IGNORECASE)
        matches: list[str] = []
        for line in proc.stdout.splitlines():
            m = pattern.match(line)
            if m:
                proto, pid = m.group(1).upper(), m.group(2)
                matches.append(f"{proto} PID {pid}")
        if matches:
            return ", ".join(dict.fromkeys(matches))
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def check_port_availability(port: int, host: str = "0.0.0.0") -> dict[str, Any]:
    """
    Check whether TCP and UDP ports can be bound locally.
    Returns dict with tcp_free, udp_free, free (both), errors, and optional owner hint.
    """
    result: dict[str, Any] = {
        "port": port,
        "host": host,
        "tcp_free": False,
        "udp_free": False,
        "free": False,
        "tcp_error": None,
        "udp_error": None,
        "owner_hint": None,
    }

    # Check TCP bind
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        tcp_sock.bind((host, port))
        result["tcp_free"] = True
    except OSError as exc:
        result["tcp_error"] = str(exc)
    finally:
        tcp_sock.close()

    # Check UDP bind
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        udp_sock.bind((host, port))
        result["udp_free"] = True
    except OSError as exc:
        result["udp_error"] = str(exc)
    finally:
        udp_sock.close()

    result["free"] = result["tcp_free"] and result["udp_free"]
    if not result["free"]:
        result["owner_hint"] = _find_port_owner_windows(port)
    return result


def resolve_map_path(map_arg: str) -> str:
    """Resolve short map alias (e.g. 'west_coast_usa') or return raw BeamNG level info.json path."""
    key = map_arg.strip().lower()
    if key in KNOWN_MAPS:
        return KNOWN_MAPS[key]
    if map_arg.startswith("/levels/") and map_arg.endswith(".json"):
        return map_arg
    if "/" not in map_arg and "\\" not in map_arg:
        return f"/levels/{map_arg.strip()}/info.json"
    return map_arg


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def generate_server_config_toml(
    *,
    server_name: str = "Private Radmin BeamMP Server",
    port: int = DEFAULT_PORT,
    max_players: int = 8,
    max_cars: int = 2,
    map_path: str = DEFAULT_MAP,
    auth_key: str = "",
    private: bool = True,
    description: str = "Private BeamMP server hosted via Radmin VPN",
    radmin_ip: str | None = None,
    bind_ip: str = "0.0.0.0",
    debug: bool = False,
    log_chat: bool = True,
    tags: str = "Freeroam,RadminVPN,Private",
) -> str:
    """Generate a clean, valid BeamMP ServerConfig.toml string."""
    resolved_map = resolve_map_path(map_path)
    connect_hint = f"{radmin_ip}:{port}" if radmin_ip else f"<YOUR_26.x.x.x_RADMIN_IP>:{port}"

    lines = [
        "# Generated by beammp-radmin-helper (Free OSS Lite Edition)",
        f"# Friends Direct Connect in BeamMP: {connect_hint}",
        "",
        "[General]",
        f'Name = "{_toml_escape(server_name)}"',
        f"Port = {port}",
        "AllowGuests = true",
        f"LogChat = {'true' if log_chat else 'false'}",
        f"Debug = {'true' if debug else 'false'}",
        f'IP = "{_toml_escape(bind_ip)}"',
        f"Private = {'true' if private else 'false'}",
        "InformationPacket = true",
        f"MaxCars = {max_cars}",
        f"MaxPlayers = {max_players}",
        f'Map = "{_toml_escape(resolved_map)}"',
        f'Description = "{_toml_escape(description)}"',
        'ResourceFolder = "Resources"',
        f'Tags = "{_toml_escape(tags)}"',
        f'AuthKey = "{_toml_escape(auth_key)}"',
        "",
        "[Misc]",
        "ImScaredOfUpdates = false",
        "SendErrorsShowMessage = true",
        "SendErrors = true",
        "",
    ]
    return "\n".join(lines)


def run_self_test() -> int:
    """Execute built-in self-tests for IP parsing, port checks, and TOML generation."""
    print("[SELF-TEST] Running beammp-radmin-helper verification suite...")
    failures: list[str] = []

    # 1. Test Radmin IP extraction from realistic Windows ipconfig output
    sample_ipconfig = """
Windows IP Configuration

Ethernet adapter Ethernet:

   Connection-specific DNS Suffix  . : lan
   IPv4 Address. . . . . . . . . . . : 192.168.1.42
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.1.1

Ethernet adapter Radmin VPN:

   Connection-specific DNS Suffix  . :
   IPv4 Address. . . . . . . . . . . : 26.142.88.19
   Subnet Mask . . . . . . . . . . . : 255.0.0.0
   Default Gateway . . . . . . . . . :
"""
    parsed = extract_radmin_ips_from_text(sample_ipconfig)
    if not parsed or parsed[0]["ip"] != "26.142.88.19" or parsed[0]["confidence"] != "high":
        failures.append(f"Expected high-confidence 26.142.88.19, got: {parsed}")
    else:
        print("  [PASS] Radmin IP extraction from Windows ipconfig output")

    # 2. Test Radmin IP range validation
    if not is_radmin_ip("26.0.0.1") or is_radmin_ip("192.168.1.1") or is_radmin_ip("not-an-ip"):
        failures.append("is_radmin_ip validation failed")
    else:
        print("  [PASS] Radmin 26.0.0.0/8 CIDR validation")

    # 3. Test live port availability check (occupied vs free ephemeral port)
    occupied_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied_tcp.bind(("127.0.0.1", 0))
    occupied_tcp.listen(1)
    test_port = occupied_tcp.getsockname()[1]
    try:
        busy_check = check_port_availability(test_port, host="127.0.0.1")
        if busy_check["tcp_free"] or busy_check["free"]:
            failures.append(f"Expected port {test_port} TCP to be detected as busy: {busy_check}")
        else:
            print(f"  [PASS] Busy TCP port detection on 127.0.0.1:{test_port}")
    finally:
        occupied_tcp.close()

    free_check = check_port_availability(test_port, host="127.0.0.1")
    if not free_check["free"]:
        failures.append(f"Expected released port {test_port} to be free: {free_check}")
    else:
        print(f"  [PASS] Free TCP+UDP port detection on 127.0.0.1:{test_port}")

    # 4. Test real host Radmin scan & port 30814 check (non-fatal if Radmin not installed)
    host_ips = detect_radmin_ips()
    port_30814 = check_port_availability(DEFAULT_PORT)
    print(f"  [INFO] Live Radmin IPs on this host: {host_ips if host_ips else 'none detected'}")
    print(
        f"  [INFO] Live port {DEFAULT_PORT} status: "
        f"TCP={'free' if port_30814['tcp_free'] else 'busy'}, "
        f"UDP={'free' if port_30814['udp_free'] else 'busy'}"
    )

    # 5. Test ServerConfig.toml generation & file write
    toml_text = generate_server_config_toml(
        server_name='Drift "Test" Server',
        port=30814,
        max_players=6,
        max_cars=2,
        map_path="italy",
        radmin_ip="26.142.88.19",
    )
    required_fragments = [
        "[General]",
        'Name = "Drift \\"Test\\" Server"',
        "Port = 30814",
        "Private = true",
        'Map = "/levels/italy/info.json"',
        "MaxPlayers = 6",
        "MaxCars = 2",
        "26.142.88.19:30814",
    ]
    missing = [frag for frag in required_fragments if frag not in toml_text]
    if missing:
        failures.append(f"Generated ServerConfig.toml missing fragments: {missing}")
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "ServerConfig.toml"
            out_path.write_text(toml_text, encoding="utf-8")
            if not out_path.is_file() or out_path.read_text(encoding="utf-8") != toml_text:
                failures.append("Failed to write/verify ServerConfig.toml in temp directory")
            else:
                print("  [PASS] ServerConfig.toml generation, escaping, and disk write")

    if failures:
        print("\n[SELF-TEST FAILED]")
        for err in failures:
            print(f"  - {err}")
        return 1

    print("\n[SELF-TEST PASSED] 100% PASS (all checks succeeded).")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beammp_radmin_helper.py",
        description="Free BeamMP + Radmin VPN diagnostic & ServerConfig.toml generator.",
    )
    parser.add_argument("--ip", help="Override Radmin VPN IPv4 (26.x.x.x) instead of auto-detecting")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="BeamMP server port (default: 30814)")
    parser.add_argument("--name", default="Private Radmin BeamMP Server", help="Server display name")
    parser.add_argument("--max-players", type=int, default=8, help="Max players (default: 8)")
    parser.add_argument("--max-cars", type=int, default=2, help="Max cars per player (default: 2)")
    parser.add_argument(
        "--map",
        default="west_coast_usa",
        help=f"Map shortcut ({', '.join(sorted(KNOWN_MAPS))}) or /levels/.../info.json",
    )
    parser.add_argument("--auth-key", default="", help="Optional BeamMP Keymaster AuthKey")
    parser.add_argument("--public", action="store_true", help="Set Private = false (requires AuthKey)")
    parser.add_argument("--out", default="ServerConfig.toml", help="Output TOML file path (default: ServerConfig.toml)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing ServerConfig.toml if present")
    parser.add_argument("--check-only", action="store_true", help="Only detect Radmin IP and check port; do not write file")
    parser.add_argument("--json", action="store_true", help="Print diagnostic result as JSON")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-tests and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio_utf8()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not (1 <= args.port <= 65535):
        print(f"[ERROR] Port must be between 1 and 65535, got {args.port}", file=sys.stderr)
        return 2

    detected = detect_radmin_ips()
    chosen_ip = args.ip.strip() if args.ip else (detected[0]["ip"] if detected else None)
    port_status = check_port_availability(args.port)

    config_text = generate_server_config_toml(
        server_name=args.name,
        port=args.port,
        max_players=args.max_players,
        max_cars=args.max_cars,
        map_path=args.map,
        auth_key=args.auth_key,
        private=not args.public,
        radmin_ip=chosen_ip,
    )

    wrote_file = False
    out_path = Path(args.out)
    write_note = ""

    if not args.check_only:
        if out_path.exists() and not args.force:
            write_note = f"Skipped writing '{out_path}' (already exists; pass --force to overwrite)."
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(config_text, encoding="utf-8")
            wrote_file = True
            write_note = f"Written '{out_path.resolve()}'."

    if args.json:
        payload = {
            "radmin_ips_detected": detected,
            "selected_radmin_ip": chosen_ip,
            "port_check": port_status,
            "wrote_file": wrote_file,
            "output_path": str(out_path),
            "note": write_note,
            "direct_connect": f"{chosen_ip}:{args.port}" if chosen_ip else None,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("=" * 64)
    print("  BeamMP Radmin VPN Helper (Free OSS Lite Edition)")
    print("=" * 64)
    if detected:
        print("[Radmin VPN] Detected 26.x.x.x IP(s):")
        for item in detected:
            print(f"  - {item['ip']}  ({item['adapter']}, confidence={item['confidence']})")
    elif chosen_ip:
        print(f"[Radmin VPN] Using provided IP: {chosen_ip}")
    else:
        print("[Radmin VPN] No active 26.x.x.x Radmin VPN IP detected.")
        print("  -> Start Radmin VPN and join/create a network, then re-run.")

    print(f"\n[Port {args.port} Check]")
    print(f"  - TCP {args.port}: {'FREE' if port_status['tcp_free'] else 'OCCUPIED'}")
    print(f"  - UDP {args.port}: {'FREE' if port_status['udp_free'] else 'OCCUPIED'}")
    if port_status["owner_hint"]:
        print(f"  - Occupied by: {port_status['owner_hint']}")
    if not port_status["free"]:
        print("  -> Hint: Close any running BeamMP-Server.exe or choose another --port.")

    if args.public and not args.auth_key:
        print("\n[WARNING] --public (Private=false) requires a valid --auth-key from BeamMP Keymaster!")

    if not args.check_only:
        print(f"\n[Config] {write_note}")

    print("\n[Friends Direct Connect]")
    if chosen_ip:
        print(f"  Share in Radmin VPN chat -> {chosen_ip}:{args.port}")
    else:
        print(f"  Share in Radmin VPN chat -> <YOUR_26.x.x.x_IP>:{args.port}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
