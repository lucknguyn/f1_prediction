"""Đồng bộ nguồn theo TTL; tiến trình riêng không ảnh hưởng cache FastF1 của web."""
from __future__ import annotations
import fcntl
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone

import pandas as pd
from .config import AppConfig


def now_utc():
    return datetime.now(timezone.utc)


class SyncService:
    interval = 900

    def __init__(self, db, config=None, ingest=None, collector=None, clock=now_utc):
        self.db, self.config, self.clock = db, config or AppConfig(), clock
        self.ingest, self.collector = ingest, collector
        self.folder = self.config.processed_dir

    def status(self):
        try:
            return json.loads((self.folder / 'sync_status.json').read_text())
        except (FileNotFoundError, ValueError):
            return {}

    def write_status(self, state):
        path = self.folder / 'sync_status.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        tmp.replace(path)

    def run(self, force=False):
        self.folder.mkdir(parents=True, exist_ok=True)
        with (self.folder / 'sync.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {'status': 'running'}
            state, now = self.status(), self.clock()
            if not force and state.get('last_attempt'):
                elapsed = (now - datetime.fromisoformat(state['last_attempt'])).total_seconds()
                if 0 <= elapsed < self.interval:
                    return state
            state.update(status='running', last_attempt=now.isoformat(), interval_seconds=self.interval)
            self.write_status(state)
            try:
                from .ingest import IngestionService
                from .weekend import WeekendCollector
                service = self.ingest or IngestionService(self.db, self.config)
                collector = self.collector or WeekendCollector(self.db, self.config)
                year = now.year
                service.ingest(year, refresh=True)
                collector.collect([year], schedule_only=True)
                sessions = collector.repository.sessions()
                recent = sessions[(sessions.season == year) &
                    (sessions.start_utc <= pd.Timestamp(now).tz_localize(None))]
                rounds = recent.drop_duplicates('race_id').tail(2).season_round.astype(int).tolist()
                # Luôn lấy lại Q/R; FP/Sprint chỉ tải phiên chưa sẵn sàng ở hai chặng gần nhất.
                reports = collector.collect([year], kinds=['Q', 'R'], refresh=True)
                if rounds:
                    reports += collector.collect([year], rounds=rounds, kinds=['FP1', 'FP2', 'FP3', 'SQ', 'S'])
                problems = [row for row in reports if row['status'] in ('unavailable', 'partial')]
                state.update(status='partial' if problems else 'ok', last_calendar_success=now.isoformat(),
                             issues=problems, year=year, error=None)
                if not problems:
                    state['last_success'] = now.isoformat()
            except Exception as exc:
                # Dữ liệu đã lưu vẫn dùng được; lần thử lỗi không làm mới mốc thành công.
                state.update(status='error', error=f'{type(exc).__name__}: {str(exc)[:300]}')
            state['finished_at'] = self.clock().isoformat()
            self.write_status(state)
            return state


class SyncWorker:
    """Một worker/cache_resource mỗi web process; file lock ngăn trùng giữa nhiều process."""
    def __init__(self, config=None):
        self.config = config or AppConfig()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, name='f1-source-sync', daemon=True)
        self.thread.start()

    def loop(self):
        folder = self.config.root / 'logs'
        folder.mkdir(exist_ok=True)
        while not self.stop_event.is_set():
            with (folder / 'sync.log').open('a') as log:
                try:
                    subprocess.run([sys.executable, '-m', 'f1lab', 'sync'], cwd=self.config.root,
                                   stdout=log, stderr=log, timeout=600, check=False)
                except subprocess.TimeoutExpired:
                    # Lần kế tiếp lấy được lock sau khi subprocess bị kết thúc.
                    log.write('Đồng bộ quá 10 phút; thử lại ở chu kỳ sau.\n')
            self.stop_event.wait(60)
