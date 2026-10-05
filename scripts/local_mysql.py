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

class LocalMySQLManager:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
        self.local = self.root / ".local"
        self.data = self.local / "mysql"
        self.socket = self.local / "mysql.sock"
        self.pid = self.local / "mysql.pid"

    def start(self):
        binary = shutil.which("mysqld")
        if not binary:
            raise SystemExit("Cần cài MySQL hoặc dùng compose.yaml rồi cấu hình self.dataBASE_URL.")
        self.local.mkdir(mode=0o700, exist_ok=True)
        os.chmod(self.local, 0o700)
        if not (self.data / "mysql").exists():
            subprocess.run([binary, "--no-defaults", "--initialize-insecure", f"--datadir={self.data}"], check=True)
        if not self.socket.exists():
            with (self.local / "mysql-launch.log").open("a") as log:
                subprocess.Popen([binary, "--no-defaults", f"--datadir={self.data}", f"--socket={self.socket}",
                                  f"--pid-file={self.pid}", "--skip-networking", "--mysqlx=0",
                                  f"--log-error={self.local / 'mysql.log'}"], stdout=log, stderr=log, start_new_session=True)
        for _ in range(40):
            if self.socket.exists():
                break
            time.sleep(0.5)
        admin_file = self.local / "admin_password"
        admin = admin_file.read_text().strip() if admin_file.exists() else ""
        try:
            connection = pymysql.connect(unix_socket=str(self.socket), user="root", password=admin, autocommit=True)
        except pymysql.MySQLError as exc:
            raise SystemExit(f"MySQL chưa sẵn sàng; xem .local/mysql.log ({type(exc).__name__}).") from exc
        with connection, connection.cursor() as cur:
            if not admin:
                admin = secrets.token_hex(24)
                cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (admin,))
                admin_file.write_text(admin)
                os.chmod(admin_file, 0o600)
            cur.execute("CREATE self.dataBASE IF NOT EXISTS f1_prediction CHARACTER SET utf8mb4")
            if not (self.root / ".env").exists():
                password = secrets.token_hex(24)
                cur.execute("CREATE USER IF NOT EXISTS 'f1'@'localhost' IDENTIFIED BY %s", (password,))
                cur.execute("ALTER USER 'f1'@'localhost' IDENTIFIED BY %s", (password,))
                cur.execute("GRANT ALL PRIVILEGES ON f1_prediction.* TO 'f1'@'localhost'")
                (self.root / ".env").write_text(f"self.dataBASE_URL=mysql+pymysql://f1:{password}@localhost/f1_prediction?unix_socket={quote(str(self.socket), safe='')}&charset=utf8mb4\n")
                os.chmod(self.root / ".env", 0o600)
        print("MySQL riêng sẵn sàng qua Unix socket. Cấu hình ứng dụng: .env (không commit).")


    def stop(self):
        if self.pid.exists():
            # pidfile thuộc datadir riêng của dự án, không dò hay dừng MySQL khác.
            os.kill(int(self.pid.read_text()), signal.SIGTERM)
            print("Đã gửi lệnh dừng MySQL riêng của dự án.")
        else:
            print("MySQL riêng chưa chạy.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop"])
    args = parser.parse_args()
    manager = LocalMySQLManager()
    manager.start() if args.action == "start" else manager.stop()
