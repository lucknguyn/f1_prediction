"""MySQL riêng trong .local, socket riêng, không đụng database có sẵn."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import time
from urllib.parse import quote

import pymysql

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DATA = LOCAL / "mysql"
SOCKET = LOCAL / "mysql.sock"
PID = LOCAL / "mysql.pid"


def start():
    binary = shutil.which("mysqld")
    if not binary:
        raise SystemExit("Cần cài MySQL hoặc dùng compose.yaml rồi cấu hình DATABASE_URL.")
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    os.chmod(LOCAL, 0o700)
    if not (DATA / "mysql").exists():
        subprocess.run([binary, "--no-defaults", "--initialize-insecure", f"--datadir={DATA}"], check=True)
    if not SOCKET.exists():
        with (LOCAL / "mysql-launch.log").open("a") as log:
            subprocess.Popen([binary, "--no-defaults", f"--datadir={DATA}", f"--socket={SOCKET}",
                              f"--pid-file={PID}", "--skip-networking", "--mysqlx=0",
                              f"--log-error={LOCAL / 'mysql.log'}"], stdout=log, stderr=log, start_new_session=True)
    for _ in range(40):
        if SOCKET.exists():
            break
        time.sleep(0.5)
    admin_file = LOCAL / "admin_password"
    admin = admin_file.read_text().strip() if admin_file.exists() else ""
    try:
        connection = pymysql.connect(unix_socket=str(SOCKET), user="root", password=admin, autocommit=True)
    except pymysql.MySQLError as exc:
        raise SystemExit(f"MySQL chưa sẵn sàng; xem .local/mysql.log ({type(exc).__name__}).") from exc
    with connection, connection.cursor() as cur:
        if not admin:
            admin = secrets.token_hex(24)
            cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (admin,))
            admin_file.write_text(admin)
            os.chmod(admin_file, 0o600)
        cur.execute("CREATE DATABASE IF NOT EXISTS f1_prediction CHARACTER SET utf8mb4")
        if not (ROOT / ".env").exists():
            password = secrets.token_hex(24)
            cur.execute("CREATE USER IF NOT EXISTS 'f1'@'localhost' IDENTIFIED BY %s", (password,))
            cur.execute("ALTER USER 'f1'@'localhost' IDENTIFIED BY %s", (password,))
            cur.execute("GRANT ALL PRIVILEGES ON f1_prediction.* TO 'f1'@'localhost'")
            (ROOT / ".env").write_text(f"DATABASE_URL=mysql+pymysql://f1:{password}@localhost/f1_prediction?unix_socket={quote(str(SOCKET), safe='')}&charset=utf8mb4\n")
            os.chmod(ROOT / ".env", 0o600)
    print("MySQL riêng sẵn sàng qua Unix socket. Cấu hình ứng dụng: .env (không commit).")


def stop():
    if PID.exists():
        # pidfile thuộc datadir riêng của dự án, không dò hay dừng MySQL khác.
        os.kill(int(PID.read_text()), signal.SIGTERM)
        print("Đã gửi lệnh dừng MySQL riêng của dự án.")
    else:
        print("MySQL riêng chưa chạy.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop"])
    args = parser.parse_args()
    start() if args.action == "start" else stop()
