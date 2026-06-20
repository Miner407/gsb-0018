import sqlite3
import datetime
import os
import sys


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples.db')


SAMPLE_TYPE_CODES = {
    '血液': 'BL',
    '尿液': 'UR',
    '组织': 'TS',
    '唾液': 'SL',
    '粪便': 'FC',
    '脑脊液': 'CS',
    '其他': 'OT'
}


STATUS_AVAILABLE = '在库'
STATUS_BORROWED = '借出'


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_no TEXT UNIQUE NOT NULL,
            sample_type TEXT NOT NULL,
            source TEXT NOT NULL,
            collect_date TEXT NOT NULL,
            storage_location TEXT NOT NULL,
            manager TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '在库',
            created_at TEXT NOT NULL,
            remark TEXT DEFAULT ''
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_no TEXT NOT NULL,
            borrower TEXT NOT NULL,
            borrow_date TEXT NOT NULL,
            return_date TEXT,
            purpose TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT '借出中',
            FOREIGN KEY (sample_no) REFERENCES samples(sample_no)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sample_no ON samples(sample_no)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sample_type ON samples(sample_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_manager ON samples(manager)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_location ON samples(storage_location)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_borrow_sample_no ON borrow_records(sample_no)')

    conn.commit()
    conn.close()


def generate_sample_no(sample_type):
    type_code = SAMPLE_TYPE_CODES.get(sample_type, 'OT')
    now = datetime.datetime.now()
    year_month = now.strftime('%Y%m')

    conn = get_db_connection()
    cursor = conn.cursor()

    prefix = f'{type_code}{year_month}'
    cursor.execute(
        "SELECT sample_no FROM samples WHERE sample_no LIKE ? ORDER BY sample_no DESC LIMIT 1",
        (f'{prefix}%',)
    )
    row = cursor.fetchone()

    if row:
        last_no = row['sample_no']
        seq = int(last_no[-4:]) + 1
    else:
        seq = 1

    sample_no = f'{prefix}{seq:04d}'

    cursor.execute("SELECT COUNT(*) as count FROM samples WHERE sample_no = ?", (sample_no,))
    if cursor.fetchone()['count'] > 0:
        for i in range(seq + 1, 10000):
            candidate = f'{prefix}{i:04d}'
            cursor.execute("SELECT COUNT(*) as count FROM samples WHERE sample_no = ?", (candidate,))
            if cursor.fetchone()['count'] == 0:
                sample_no = candidate
                break

    conn.close()
    return sample_no


def add_sample(sample_type, source, collect_date, storage_location, manager, remark=''):
    if sample_type not in SAMPLE_TYPE_CODES:
        return False, f'样本类型无效，可选类型：{", ".join(SAMPLE_TYPE_CODES.keys())}'

    try:
        datetime.datetime.strptime(collect_date, '%Y-%m-%d')
    except ValueError:
        return False, '采集日期格式错误，请使用 YYYY-MM-DD 格式'

    sample_no = generate_sample_no(sample_type)
    created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            '''INSERT INTO samples (sample_no, sample_type, source, collect_date, 
               storage_location, manager, status, created_at, remark)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (sample_no, sample_type, source, collect_date,
             storage_location, manager, STATUS_AVAILABLE, created_at, remark)
        )
        conn.commit()
        return True, sample_no
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return False, f'编号冲突错误: {e}'
    finally:
        conn.close()


def query_samples(sample_type=None, manager=None, location=None, status=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM samples WHERE 1=1"
    params = []

    if sample_type:
        query += " AND sample_type = ?"
        params.append(sample_type)
    if manager:
        query += " AND manager LIKE ?"
        params.append(f'%{manager}%')
    if location:
        query += " AND storage_location LIKE ?"
        params.append(f'%{location}%')
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_sample_by_no(sample_no):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM samples WHERE sample_no = ?", (sample_no,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def borrow_sample(sample_no, borrower, purpose=''):
    sample = get_sample_by_no(sample_no)
    if not sample:
        return False, '样本不存在'

    if sample['status'] == STATUS_BORROWED:
        return False, '该样本已被借出，无法重复借出'

    borrow_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE samples SET status = ? WHERE sample_no = ?",
            (STATUS_BORROWED, sample_no)
        )

        cursor.execute(
            '''INSERT INTO borrow_records (sample_no, borrower, borrow_date, purpose, status)
               VALUES (?, ?, ?, ?, ?)''',
            (sample_no, borrower, borrow_date, purpose, '借出中')
        )

        conn.commit()
        return True, '借出成功'
    except Exception as e:
        conn.rollback()
        return False, f'借出失败: {e}'
    finally:
        conn.close()


def return_sample(sample_no):
    sample = get_sample_by_no(sample_no)
    if not sample:
        return False, '样本不存在'

    if sample['status'] == STATUS_AVAILABLE:
        return False, '该样本已在库，无需归还'

    return_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE samples SET status = ? WHERE sample_no = ?",
            (STATUS_AVAILABLE, sample_no)
        )

        cursor.execute(
            '''SELECT id FROM borrow_records
               WHERE sample_no = ? AND status = '借出中'
               ORDER BY id DESC LIMIT 1''',
            (sample_no,)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                '''UPDATE borrow_records SET status = '已归还', return_date = ?
                   WHERE id = ?''',
                (return_date, row['id'])
            )

        conn.commit()
        return True, '归还成功'
    except Exception as e:
        conn.rollback()
        return False, f'归还失败: {e}'
    finally:
        conn.close()


def get_borrow_records(sample_no=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if sample_no:
        cursor.execute(
            "SELECT * FROM borrow_records WHERE sample_no = ? ORDER BY borrow_date DESC",
            (sample_no,)
        )
    else:
        cursor.execute("SELECT * FROM borrow_records ORDER BY borrow_date DESC")

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def list_all_sample_types():
    return list(SAMPLE_TYPE_CODES.keys())


def print_sample_table(samples):
    if not samples:
        print('  没有找到匹配的样本记录')
        return

    headers = ['编号', '类型', '来源', '采集日期', '保存位置', '负责人', '状态']
    col_widths = [16, 8, 16, 12, 16, 10, 6]

    header_line = ' | '.join(h.ljust(w) for h, w in zip(headers, col_widths))
    print('  ' + header_line)
    print('  ' + '-' * len(header_line))

    for s in samples:
        row = [
            s['sample_no'].ljust(16),
            s['sample_type'].ljust(8),
            (s['source'][:14] + '..' if len(s['source']) > 16 else s['source']).ljust(16),
            s['collect_date'].ljust(12),
            (s['storage_location'][:14] + '..' if len(s['storage_location']) > 16 else s['storage_location']).ljust(16),
            s['manager'].ljust(10),
            s['status'].ljust(6)
        ]
        print('  ' + ' | '.join(row))


def print_borrow_records_table(records):
    if not records:
        print('  没有找到借还记录')
        return

    headers = ['记录ID', '样本编号', '借用人', '借出时间', '归还时间', '用途', '状态']
    col_widths = [8, 16, 12, 20, 20, 20, 8]

    header_line = ' | '.join(h.ljust(w) for h, w in zip(headers, col_widths))
    print('  ' + header_line)
    print('  ' + '-' * len(header_line))

    for r in records:
        purpose = r['purpose'] or ''
        return_date = r['return_date'] or '未归还'
        row = [
            str(r['id']).ljust(8),
            r['sample_no'].ljust(16),
            r['borrower'].ljust(12),
            r['borrow_date'].ljust(20),
            return_date.ljust(20),
            (purpose[:18] + '..' if len(purpose) > 20 else purpose).ljust(20),
            r['status'].ljust(8)
        ]
        print('  ' + ' | '.join(row))


def input_with_default(prompt, default=None):
    if default:
        result = input(f'{prompt} (默认: {default}): ').strip()
        return result if result else default
    else:
        while True:
            result = input(f'{prompt}: ').strip()
            if result:
                return result
            print('  输入不能为空，请重新输入')


def menu_add_sample():
    print('\n=== 登记新样本 ===')

    print('  可选样本类型:')
    for i, st in enumerate(list_all_sample_types(), 1):
        print(f'    {i}. {st}')

    while True:
        type_choice = input('  请选择样本类型编号: ').strip()
        try:
            idx = int(type_choice) - 1
            if 0 <= idx < len(SAMPLE_TYPE_CODES):
                sample_type = list(SAMPLE_TYPE_CODES.keys())[idx]
                break
            else:
                print('  选择无效，请重新输入')
        except ValueError:
            print('  请输入数字编号')

    source = input_with_default('  样本来源')
    collect_date = input_with_default('  采集日期 (YYYY-MM-DD)', datetime.date.today().strftime('%Y-%m-%d'))
    storage_location = input_with_default('  保存位置')
    manager = input_with_default('  负责人')
    remark = input('  备注 (可选): ').strip()

    success, result = add_sample(
        sample_type, source, collect_date, storage_location, manager, remark
    )

    if success:
        print(f'\n  [OK] 样本登记成功！样本编号: {result}')
    else:
        print(f'\n  [FAIL] 登记失败: {result}')


def menu_query_samples():
    print('\n=== 查询样本 ===')
    print('  可按以下条件查询（留空表示不限制）')

    print('  可选样本类型:')
    for i, st in enumerate(['全部'] + list_all_sample_types(), 0):
        print(f'    {i}. {st}')

    sample_type = None
    while True:
        type_choice = input('  样本类型编号 (默认0): ').strip()
        if not type_choice or type_choice == '0':
            sample_type = None
            break
        try:
            idx = int(type_choice) - 1
            if 0 <= idx < len(SAMPLE_TYPE_CODES):
                sample_type = list(SAMPLE_TYPE_CODES.keys())[idx]
                break
            else:
                print('  选择无效，请重新输入')
        except ValueError:
            print('  请输入数字编号')

    manager = input('  负责人 (支持模糊搜索，留空不限制): ').strip() or None
    location = input('  保存位置 (支持模糊搜索，留空不限制): ').strip() or None

    print('  状态筛选:')
    print('    0. 全部')
    print('    1. 在库')
    print('    2. 借出')
    status = None
    while True:
        status_choice = input('  请选择 (默认0): ').strip()
        if not status_choice or status_choice == '0':
            status = None
            break
        elif status_choice == '1':
            status = STATUS_AVAILABLE
            break
        elif status_choice == '2':
            status = STATUS_BORROWED
            break
        else:
            print('  选择无效，请重新输入')

    samples = query_samples(sample_type, manager, location, status)
    print(f'\n  查询结果: 共 {len(samples)} 条记录')
    print_sample_table(samples)


def menu_borrow_sample():
    print('\n=== 样本借出 ===')
    sample_no = input_with_default('  样本编号').upper()

    sample = get_sample_by_no(sample_no)
    if not sample:
        print('  [FAIL] 样本不存在')
        return

    print(f'  样本信息: {sample["sample_type"]} - {sample["source"]}')
    print(f'  当前状态: {sample["status"]}')

    if sample['status'] == STATUS_BORROWED:
        print('  [FAIL] 该样本已被借出，无法重复借出')
        return

    borrower = input_with_default('  借用人')
    purpose = input('  借出用途 (可选): ').strip()

    success, msg = borrow_sample(sample_no, borrower, purpose)
    if success:
        print(f'  [OK] {msg}')
    else:
        print(f'  [FAIL] {msg}')


def menu_return_sample():
    print('\n=== 样本归还 ===')
    sample_no = input_with_default('  样本编号').upper()

    sample = get_sample_by_no(sample_no)
    if not sample:
        print('  [FAIL] 样本不存在')
        return

    print(f'  样本信息: {sample["sample_type"]} - {sample["source"]}')
    print(f'  当前状态: {sample["status"]}')

    if sample['status'] == STATUS_AVAILABLE:
        print('  [FAIL] 该样本已在库，无需归还')
        return

    confirm = input('  确认归还? (y/n): ').strip().lower()
    if confirm != 'y':
        print('  已取消归还')
        return

    success, msg = return_sample(sample_no)
    if success:
        print(f'  [OK] {msg}')
    else:
        print(f'  [FAIL] {msg}')


def menu_view_records():
    print('\n=== 借还记录查询 ===')
    sample_no = input('  样本编号 (留空查询所有记录): ').strip().upper() or None

    records = get_borrow_records(sample_no)
    print(f'\n  共找到 {len(records)} 条记录')
    print_borrow_records_table(records)


def menu_sample_detail():
    print('\n=== 样本详情 ===')
    sample_no = input_with_default('  样本编号').upper()

    sample = get_sample_by_no(sample_no)
    if not sample:
        print('  [FAIL] 样本不存在')
        return

    print(f'\n  样本编号: {sample["sample_no"]}')
    print(f'  样本类型: {sample["sample_type"]}')
    print(f'  样本来源: {sample["source"]}')
    print(f'  采集日期: {sample["collect_date"]}')
    print(f'  保存位置: {sample["storage_location"]}')
    print(f'  负责人:   {sample["manager"]}')
    print(f'  当前状态: {sample["status"]}')
    print(f'  登记时间: {sample["created_at"]}')
    if sample['remark']:
        print(f'  备注:     {sample["remark"]}')

    records = get_borrow_records(sample_no)
    if records:
        print(f'\n  借还历史 ({len(records)} 条):')
        print_borrow_records_table(records)


def main():
    init_db()

    while True:
        print('\n' + '=' * 50)
        print('  实验室样本编号管理系统')
        print('=' * 50)
        print('  1. 登记新样本')
        print('  2. 查询样本')
        print('  3. 查看样本详情')
        print('  4. 样本借出')
        print('  5. 样本归还')
        print('  6. 查询借还记录')
        print('  0. 退出系统')
        print('-' * 50)

        choice = input('  请选择操作 [0-6]: ').strip()

        if choice == '1':
            menu_add_sample()
        elif choice == '2':
            menu_query_samples()
        elif choice == '3':
            menu_sample_detail()
        elif choice == '4':
            menu_borrow_sample()
        elif choice == '5':
            menu_return_sample()
        elif choice == '6':
            menu_view_records()
        elif choice == '0':
            print('\n  感谢使用，再见！')
            sys.exit(0)
        else:
            print('  无效的选择，请重新输入')

        input('\n  按回车键继续...')


if __name__ == '__main__':
    main()
