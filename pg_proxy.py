"""
pg_proxy.py - TCP proxy: forwards 172.17.0.1:5433 → 127.0.0.1:5432
Run this on Windows as a background task so WSL can reach PostgreSQL.
"""
import socket
import threading
import sys

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 5433
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 5432
BUFSIZE = 65536

def pipe(src, dst):
    try:
        while True:
            data = src.recv(BUFSIZE)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle(client_sock, addr):
    try:
        server_sock = socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=10)
        t1 = threading.Thread(target=pipe, args=(client_sock, server_sock), daemon=True)
        t2 = threading.Thread(target=pipe, args=(server_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
    except Exception as e:
        print(f"[proxy] connect error: {e}")
        client_sock.close()

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, LISTEN_PORT))
    srv.listen(32)
    print(f"[pg_proxy] listening on {LISTEN_HOST}:{LISTEN_PORT} → {TARGET_HOST}:{TARGET_PORT}", flush=True)
    while True:
        client_sock, addr = srv.accept()
        threading.Thread(target=handle, args=(client_sock, addr), daemon=True).start()

if __name__ == "__main__":
    main()
