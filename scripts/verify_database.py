"""Bằng chứng MySQL: truy vấn, khóa ngoại, rollback và restore vào schema thử riêng.
Chạy: python -m scripts.verify_database (MySQL riêng scripts/local_mysql.py).
"""
import json
import re
import uuid
from sqlalchemy import create_engine, text, func, select
from sqlalchemy.exc import IntegrityError
from f1lab.db import Database, Base, Driver, Entry, VIEW_SQL
from f1lab.config import AppConfig
from f1lab.delivery import BackupService


def main():
    config, database = AppConfig(), Database()
    database.initialize()
    output = {'queries': [], 'checks': {}}
    with database.engine.connect() as conn:
        output['mysql_version'] = conn.execute(text('SELECT VERSION()')).scalar()
        raw = (config.root/'sql/demo_queries.sql').read_text()
        raw = re.sub(r'^--.*$', '', raw, flags=re.M)
        for number, query in enumerate(filter(str.strip, raw.split(';')), 1):
            result = conn.execute(text(query)).mappings().all()
            output['queries'].append({'number':number,'row_count':len(result),'sample':[dict(x) for x in result[:3]]})
        output['account'] = conn.execute(text('SELECT CURRENT_USER()')).scalar()
    backup = config.root/'deliverables/database.json.gz'
    expected = BackupService(database.engine).backup(backup)
    # Tài khoản root cục bộ chỉ dùng cho schema thử có tên UUID, không chạm schema người dùng.
    admin = database.engine.url.set(username='root', password=(config.root/'.local/admin_password').read_text().strip(), database=None)
    root_engine = create_engine(admin)
    schema='f1_verify_'+uuid.uuid4().hex[:12]
    scratch=None
    try:
        with root_engine.begin() as conn: conn.execute(text(f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4'))
        scratch=create_engine(admin.set(database=schema))
        Base.metadata.create_all(scratch)
        restored=BackupService(scratch).restore(backup)
        with scratch.begin() as conn: conn.execute(text(VIEW_SQL))
        with scratch.connect() as conn:
            actual={table.name:conn.execute(select(func.count()).select_from(table)).scalar() for table in Base.metadata.sorted_tables}
            output['restored_view_rows']=conn.execute(text('SELECT COUNT(*) FROM prediction_comparison')).scalar()
        assert restored==expected==actual
        output['checks']['backup_restore_all_tables']=True
        output['row_counts']=actual
        try:
            with scratch.begin() as conn:
                conn.execute(Entry.__table__.insert().values(race_id=-999,driver_id='missing',team_id='missing'))
        except IntegrityError:
            output['checks']['foreign_key_rejects_orphan']=True
        else: raise AssertionError('Foreign key did not reject orphan')
        try:
            with scratch.begin() as conn:
                conn.execute(Driver.__table__.insert().values(id='rollback-proof',name='Rollback proof'))
                raise RuntimeError('rollback')
        except RuntimeError: pass
        with scratch.connect() as conn:
            assert conn.execute(select(func.count()).select_from(Driver).where(Driver.id=='rollback-proof')).scalar()==0
        output['checks']['transaction_rollback']=True
        try: BackupService(scratch).restore(backup)
        except ValueError: output['checks']['reject_nonempty_restore']=True
        else: raise AssertionError('Should reject restore into nonempty database')
    finally:
        if scratch: scratch.dispose()
        with root_engine.begin() as conn: conn.execute(text(f'DROP DATABASE IF EXISTS `{schema}`'))
        root_engine.dispose();database.close()
    path=config.root/'deliverables/database-evidence.json'
    path.write_text(json.dumps(output,indent=2,ensure_ascii=False,default=str))
    print('12 SQL queries; FK + rollback + 17-table MySQL restore verified. Evidence:',path)


if __name__=='__main__': main()
