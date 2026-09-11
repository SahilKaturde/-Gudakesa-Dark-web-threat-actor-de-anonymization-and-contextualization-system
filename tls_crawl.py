#!/usr/bin/env python3
import sys
import os
import pathlib
import json
import socket
import urllib.parse
import re
import datetime
import subprocess
import shutil
import ssl
import hashlib


def validate_onion_url(url: str) -> urllib.parse.ParseResult:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("Invalid URL format.")

    if not hostname.lower().endswith(".onion"):
        raise ValueError(f"Hostname '{hostname}' is not a .onion address.")

    if len(hostname) != 62:
        print(
            f"Warning: Hostname length is {len(hostname)}, "
            f"expecting 62 for v3 onion.",
            file=sys.stderr,
        )

    return parsed


def check_proxy(host="127.0.0.1", port=15000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)

    try:
        s.connect((host, port))
        return True

    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

    finally:
        s.close()


def get_next_crawl_dir(scraped_root: pathlib.Path) -> tuple:
    scraped_root.mkdir(parents=True, exist_ok=True)

    existing = []

    for p in scraped_root.iterdir():
        if p.is_dir():
            m = re.match(r"^(\d+)_0$", p.name)

            if m:
                existing.append(int(m.group(1)))

    next_num = max(existing, default=0) + 1
    crawl_dir = scraped_root / f"{next_num}_0"

    return next_num, crawl_dir


def find_scrapy_executable(project_root: pathlib.Path) -> list:
    venv_scrapy = project_root / ".venv" / "bin" / "scrapy"

    if venv_scrapy.exists():
        return [str(venv_scrapy)]

    system_scrapy = shutil.which("scrapy")

    if system_scrapy:
        return [system_scrapy]

    return [sys.executable, "-m", "scrapy"]


def count_json_items(json_file: pathlib.Path) -> int:
    if not json_file.exists():
        return 0

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return len(data)

    except Exception:
        pass

    return 0


def count_extracted_entities(entities_file: pathlib.Path) -> int:
    if not entities_file.exists():
        return 0

    try:
        with open(entities_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            total = 0

            for record in data:
                total += len(record.get("entities", []))

            return total

    except Exception:
        pass

    return 0


def rename_html_files(html_dir: pathlib.Path) -> int:
    txt_files = sorted(list(html_dir.glob("*.txt")))

    for i, f in enumerate(txt_files, start=1):
        new_name = html_dir / f"page_{i:03d}.txt"

        # Avoid collision if already renamed
        if f != new_name:
            if new_name.exists():
                new_name.unlink()

            f.rename(new_name)

    return len(txt_files)


def clean_name(name):
    """
    Flatten an X.509 name (subject/issuer) into a plain dict.

    getpeercert() returns these as a tuple of RDNs, where each RDN is
    itself a tuple of (key, value) pairs — X.509 permits multi-valued
    RDNs, so the naive `for key, value in name` will raise ValueError on
    the very first real certificate.
    """
    if not name:
        return None

    result = {}

    for rdn in name:
        for key, value in rdn:
            result[key] = value

    return result


def parse_certificate_dates(cert):
    not_before = cert.get("notBefore")
    not_after = cert.get("notAfter")

    return {
        "not_before": not_before,
        "not_after": not_after,
    }


def extract_san(cert):
    sans = []

    for item_type, value in cert.get("subjectAltName", []):
        sans.append({
            "type": item_type,
            "value": value,
        })

    return sans


def hostname_matches(cert_dict, hostname):
    """
    SAN-only hostname match.

    ssl.match_hostname() was deprecated in 3.7 and removed in 3.12, so
    we do our own comparison. We intentionally do not fall back to CN —
    that behaviour was dropped industry-wide years ago.
    """
    hostname = hostname.lower()

    dns_names = [
        v.lower()
        for t, v in cert_dict.get("subjectAltName", [])
        if t == "DNS"
    ]

    def _matches(pattern, host):
        if pattern.startswith("*."):
            return (
                host.count(".") == pattern.count(".")
                and host.endswith(pattern[1:])
            )
        return pattern == host

    return any(_matches(p, hostname) for p in dns_names)


def analyze_tls(parsed_url, proxy_host="127.0.0.1", proxy_port=15000):
    """
    Passive TLS observation through the local Privoxy HTTP proxy.

    Records the TLS metadata exposed by the endpoint on port 443,
    regardless of whether the seed URL itself is http:// or https://.
    Most onion services serve HTTPS on 443 even when a user copies an
    http:// link, so we always probe 443 unless the URL explicitly
    names a different port. This is still a passive CONNECT through the
    same Privoxy path — nothing extra is scanned.
    """

    result = {
        "requested_url": parsed_url.geturl(),
        "hostname": parsed_url.hostname,
        "port": None,
        "scheme": parsed_url.scheme,
        "observed_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "tls_observed": False,
        "status": "NOT_ATTEMPTED",
    }

    hostname = parsed_url.hostname

    # Decide which port to probe. If the URL explicitly carries a port,
    # honour it. Otherwise always try 443 — that's where TLS lives on
    # virtually every onion service, even ones linked over http://.
    if parsed_url.scheme.lower() == "https":
        port = parsed_url.port or 443
    else:
        port = parsed_url.port or 443
        result["note"] = (
            "Seed URL is HTTP; attempting TLS observation on port 443."
        )

    result["port"] = port

    # Privoxy is an HTTP proxy. The socket connects to Privoxy,
    # which establishes the connection through its configured Tor path.
    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_sock.settimeout(15)

    try:
        proxy_sock.connect((proxy_host, proxy_port))

        connect_request = (
            f"CONNECT {hostname}:{port} HTTP/1.1\r\n"
            f"Host: {hostname}:{port}\r\n"
            f"Proxy-Connection: Keep-Alive\r\n"
            f"\r\n"
        )

        proxy_sock.sendall(connect_request.encode("ascii"))

        # Read enough to obtain the proxy response headers.
        response = b""

        while b"\r\n\r\n" not in response and len(response) < 65536:
            chunk = proxy_sock.recv(4096)

            if not chunk:
                break

            response += chunk

        response_text = response.decode("iso-8859-1", errors="replace")

        status_line = response_text.split("\r\n", 1)[0]

        result["proxy_connect_response"] = status_line

        # CONNECT should return 200 before TLS can begin.
        if not re.search(r"\s200\s", status_line):
            result["status"] = "PROXY_CONNECT_FAILED"
            result["error"] = status_line
            return result

        # Important:
        # We intentionally do not enable certificate verification here.
        # We want to observe the presented certificate, including certificates
        # that are self-signed or otherwise invalid for the requested hostname.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Advertise ALPN so the server's chosen protocol is observable.
        context.set_alpn_protocols(["h2", "http/1.1"])

        # Optional: dump handshake secrets so a simultaneous pcap can be
        # decrypted in Wireshark. The keylog file is sensitive — treat it
        # like key material, don't leave it lying around.
        keylog_path = os.environ.get("TLS_KEYLOG_FILE")
        if keylog_path:
            context.keylog_filename = keylog_path

        handshake_started = datetime.datetime.now(datetime.timezone.utc)
        tls_sock = context.wrap_socket(
            proxy_sock,
            server_hostname=hostname,
        )
        handshake_finished = datetime.datetime.now(datetime.timezone.utc)

        try:
            cert_der = tls_sock.getpeercert(binary_form=True)
            cert_dict = tls_sock.getpeercert()

            cipher = tls_sock.cipher()

            result["tls_observed"] = True
            result["status"] = "SUCCESS"

            result["tls_version"] = tls_sock.version()

            if cipher:
                result["cipher"] = {
                    "name": cipher[0],
                    "protocol": cipher[1],
                    "bits": cipher[2],
                }

            # ------------------------------------------------------------
            # Handshake summary
            # ------------------------------------------------------------

            result["handshake"] = {
                "duration_ms": round(
                    (handshake_finished - handshake_started).total_seconds()
                    * 1000,
                    2,
                ),
                "alpn_protocol": tls_sock.selected_alpn_protocol(),
                "compression": tls_sock.compression(),  # almost always None
                "session_reused": getattr(
                    tls_sock, "session_reused", None
                ),
            }

            session = tls_sock.session
            if session is not None:
                result["handshake"]["ticket_lifetime_hint"] = getattr(
                    session, "ticket_lifetime_hint", None
                )

            # Full chain, not just the leaf cert — needs Python 3.13+
            if hasattr(tls_sock, "get_unverified_chain"):
                chain = tls_sock.get_unverified_chain() or []
                result["handshake"]["chain_length"] = len(chain)
                result["handshake"]["chain_sha256"] = [
                    hashlib.sha256(der).hexdigest().upper()
                    for der in chain
                ]

            # ------------------------------------------------------------
            # Certificate
            # ------------------------------------------------------------

            result["certificate"] = {
                "sha256_fingerprint": (
                    hashlib.sha256(cert_der).hexdigest().upper()
                ),
                "subject": clean_name(cert_dict.get("subject")),
                "issuer": clean_name(cert_dict.get("issuer")),
                "san": extract_san(cert_dict),
                "serial_number": cert_dict.get("serialNumber"),
                **parse_certificate_dates(cert_dict),
            }

            # Compare requested hostname against SAN without requiring a
            # trusted CA. hostname_matches() returns a bool directly, so
            # no try/except is needed here.
            result["hostname_match"] = hostname_matches(
                cert_dict, hostname
            )

        finally:
            tls_sock.close()

    except ssl.SSLError as exc:
        result["status"] = "TLS_ERROR"
        result["error"] = str(exc)

    except socket.timeout:
        result["status"] = "TIMEOUT"
        result["error"] = "TLS observation timed out."

    except OSError as exc:
        result["status"] = "SOCKET_ERROR"
        result["error"] = str(exc)

    finally:
        try:
            proxy_sock.close()
        except Exception:
            pass

    return result


def main():
    project_root = pathlib.Path(__file__).resolve().parent.parent
    scraped_root = project_root / "scraped"

    print("=" * 50)
    print("Dark-Web Threat Intelligence Crawler")
    print("=" * 50)

    if len(sys.argv) > 1:
        raw_url = sys.argv[1]
    else:
        try:
            raw_url = input("Enter .onion URL: ").strip()

        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

    if not raw_url:
        print("Please enter a valid URL.", file=sys.stderr)
        sys.exit(1)

    try:
        parsed_url = validate_onion_url(raw_url)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    domain = parsed_url.hostname.lower()

    # ------------------------------------------------------------
    # 1. Proxy Reachability
    # ------------------------------------------------------------

    if not check_proxy("127.0.0.1", 15000):
        print(
            "Error: Privoxy endpoint 127.0.0.1:15000 is not reachable.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------
    # 2. Directory structure
    # ------------------------------------------------------------

    crawl_num, crawl_dir = get_next_crawl_dir(scraped_root)
    crawl_id = f"{crawl_num}_0"

    raw_dir = crawl_dir / "raw"
    html_dir = crawl_dir / "html"
    extracted_dir = crawl_dir / "extracted"

    raw_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    crawler_json_path = raw_dir / "crawler.json"
    metadata_json_path = crawl_dir / "metadata.json"
    tls_json_path = crawl_dir / "tls.json"
    entities_json_path = extracted_dir / "entities.json"

    print(f"Target : {raw_url}")
    print(f"Crawl  : {crawl_id}")
    print(f"Output : {crawl_dir}")
    print()

    # ------------------------------------------------------------
    # 3. Clean Environment Variables
    # ------------------------------------------------------------

    env = os.environ.copy()

    proxy_vars = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ]

    for var in proxy_vars:
        env.pop(var, None)

    env["DARKWEB_INTEL_SKIP_SEEDFETCH"] = "1"

    # ------------------------------------------------------------
    # 4. TLS observation
    # ------------------------------------------------------------

    print("Collecting TLS metadata...")

    tls_data = analyze_tls(
        parsed_url,
        proxy_host="127.0.0.1",
        proxy_port=15000,
    )

    with open(tls_json_path, "w", encoding="utf-8") as f:
        json.dump(tls_data, f, indent=2)

    if tls_data["status"] == "SUCCESS":
        print("TLS observation complete.")
        print(f"TLS version : {tls_data.get('tls_version')}")
        print(f"Probed port : {tls_data.get('port')}")

        handshake = tls_data.get("handshake", {})
        if handshake.get("alpn_protocol"):
            print(f"ALPN        : {handshake.get('alpn_protocol')}")

        if handshake.get("duration_ms") is not None:
            print(f"Handshake   : {handshake.get('duration_ms')} ms")

        certificate = tls_data.get("certificate", {})

        print(
            "Certificate : "
            f"{certificate.get('sha256_fingerprint', 'N/A')}"
        )

    else:
        print(
            f"TLS observation: {tls_data['status']}"
        )

        if tls_data.get("note"):
            print(f"Note        : {tls_data.get('note')}")

        if tls_data.get("error"):
            print(f"Detail      : {tls_data.get('error')}")

    print()

    # ------------------------------------------------------------
    # 5. Ahmia / Scrapy setup
    # ------------------------------------------------------------

    ahmia_dir = project_root / "ahmia-crawler" / "ahmia"
    scrapy_cmd = find_scrapy_executable(project_root)

    pipeline_setting = '{"ahmia.pipelines.HtmlExportPipeline":100}'

    cmd = scrapy_cmd + [
        "crawl",
        "ahmia-tor",

        "-a",
        f"seedlist={raw_url}",

        "-s",
        "DEPTH_LIMIT=1",

        "-s",
        "CONCURRENT_REQUESTS=1",

        "-s",
        "DOWNLOAD_DELAY=2",

        "-s",
        "RETRY_ENABLED=False",

        "-s",
        "DOWNLOAD_MAXSIZE=209715200",

        "-s",
        f"ITEM_PIPELINES={pipeline_setting}",

        "-s",
        f"HTML_EXPORT_DIR={html_dir.resolve()}",

        "-O",
        str(crawler_json_path.resolve()),
    ]

    now_utc = datetime.datetime.now(datetime.timezone.utc)

    started_at = now_utc.isoformat()

    status = "FAILED"
    error_msg = None

    # ------------------------------------------------------------
    # 6. Run crawler
    # ------------------------------------------------------------

    print("Starting crawler...")

    try:
        res = subprocess.run(
            cmd,
            cwd=str(ahmia_dir),
            env=env,
            capture_output=True,
            text=True,
        )

        if res.returncode == 0:
            status = "SUCCESS"
            print("Crawl completed.")

        else:
            error_msg = (
                f"Scrapy exited with code {res.returncode}:\n"
                f"{res.stderr}"
            )

            print(
                f"Crawler failed with exit code {res.returncode}.",
                file=sys.stderr,
            )

            print(
                f"Stderr: {res.stderr[:500]}...",
                file=sys.stderr,
            )

    except Exception as exc:
        error_msg = (
            f"Failed to execute crawler subprocess: {exc}"
        )

        print(
            f"Crawler execution error: {exc}",
            file=sys.stderr,
        )

    completed_at = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    # ------------------------------------------------------------
    # 7. Ensure crawler JSON exists
    # ------------------------------------------------------------

    if (
        not crawler_json_path.exists()
        or crawler_json_path.stat().st_size == 0
    ):
        with open(
            crawler_json_path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write("[]\n")

    # ------------------------------------------------------------
    # 8. Post-process HTML files
    # ------------------------------------------------------------

    html_files_count = rename_html_files(html_dir)

    # ------------------------------------------------------------
    # 9. Metadata
    # ------------------------------------------------------------

    meta = {
        "crawl_id": crawl_id,
        "seed_url": raw_url,
        "domain": domain,
        "started_at": started_at,
        "completed_at": completed_at,
        "status": status,

        "depth_limit": 1,
        "concurrent_requests": 1,
        "download_delay": 2,
        "download_maxsize_bytes": 209715200,

        "proxy": "127.0.0.1:15000",
        "crawler": "Ahmia/Scrapy",

        "pages_collected": count_json_items(
            crawler_json_path
        ),

        "html_files_saved": html_files_count,

        "tls_observation": {
            "status": tls_data.get("status"),
            "tls_observed": tls_data.get("tls_observed"),
            "tls_version": tls_data.get("tls_version"),
            "probed_port": tls_data.get("port"),
            "certificate_sha256": (
                tls_data.get("certificate", {})
                .get("sha256_fingerprint")
            ),
            "hostname_match": tls_data.get(
                "hostname_match"
            ),
            "alpn_protocol": (
                tls_data.get("handshake", {})
                .get("alpn_protocol")
            ),
            "handshake_duration_ms": (
                tls_data.get("handshake", {})
                .get("duration_ms")
            ),
            "session_reused": (
                tls_data.get("handshake", {})
                .get("session_reused")
            ),
            "chain_length": (
                tls_data.get("handshake", {})
                .get("chain_length")
            ),
        },
    }

    if error_msg:
        meta["error"] = error_msg

    with open(
        metadata_json_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(meta, f, indent=2)

    # ------------------------------------------------------------
    # 10. Entity extraction
    # ------------------------------------------------------------

    entities_count = 0

    if status == "SUCCESS":

        print("Running entity extraction...")

        extractor_script = (
            project_root /
            "intel" /
            "extractor.py"
        )

        if extractor_script.exists():

            ext_cmd = [
                sys.executable,
                str(extractor_script),
                str(crawler_json_path),
                str(entities_json_path),
            ]

            try:
                ext_res = subprocess.run(
                    ext_cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                )

                if ext_res.returncode != 0:

                    print(
                        f"Warning: Extractor failed:\n"
                        f"{ext_res.stderr}",
                        file=sys.stderr,
                    )

                else:

                    print(
                        "Entity extraction complete."
                    )

                    entities_count = (
                        count_extracted_entities(
                            entities_json_path
                        )
                    )

                    meta["entities_extracted"] = (
                        entities_count
                    )

                    with open(
                        metadata_json_path,
                        "w",
                        encoding="utf-8",
                    ) as f:
                        json.dump(
                            meta,
                            f,
                            indent=2,
                        )

            except Exception as e:

                print(
                    f"Warning: Could not run extractor: {e}",
                    file=sys.stderr,
                )

        else:

            print(
                f"Warning: Extractor script not found "
                f"at {extractor_script}",
                file=sys.stderr,
            )

    # ------------------------------------------------------------
    # 11. Summary
    # ------------------------------------------------------------

    print("\n==================================================")
    print("Crawl Summary")
    print("==================================================")

    print(f"Status            : {status}")
    print(f"Crawl ID          : {crawl_id}")
    print(f"Pages collected   : {meta['pages_collected']}")
    print(f"HTML files saved  : {html_files_count}")
    print(f"Entities extracted: {entities_count}")

    print(
        f"TLS observed      : "
        f"{tls_data.get('tls_observed')}"
    )

    print(
        f"TLS status        : "
        f"{tls_data.get('status')}"
    )

    if tls_data.get("tls_version"):
        print(
            f"TLS version       : "
            f"{tls_data.get('tls_version')}"
        )

    handshake = tls_data.get("handshake") or {}
    if handshake.get("alpn_protocol"):
        print(f"ALPN              : {handshake.get('alpn_protocol')}")

    print()
    print(f"Output directory  : {crawl_dir}")
    print("==================================================")


if __name__ == "__main__":
    main()