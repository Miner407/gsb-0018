import os
import sys
import sqlite3
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sample_manager as sm


def setup_test_db():
    test_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_samples.db')
    sm.set_db_path(test_db)
    if os.path.exists(test_db):
        os.remove(test_db)
    journal = test_db + '-journal'
    if os.path.exists(journal):
        os.remove(journal)
    wal = test_db + '-wal'
    if os.path.exists(wal):
        os.remove(wal)
    shm = test_db + '-shm'
    if os.path.exists(shm):
        os.remove(shm)
    return test_db


def cleanup_test_db(test_db):
    for suffix in ['', '-journal', '-wal', '-shm']:
        path = test_db + suffix
        if os.path.exists(path):
            os.remove(path)


def test_init():
    print('=' * 60)
    print('测试 1: 数据库初始化')
    print('-' * 60)
    sm.init_db()
    assert os.path.exists(sm.DB_PATH), '数据库文件未创建'

    conn = sqlite3.connect(sm.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert 'samples' in tables, 'samples 表未创建'
    assert 'borrow_records' in tables, 'borrow_records 表未创建'
    print('[OK] 数据库初始化成功')
    print(f'  表: {tables}')


def test_add_sample_basic():
    print('\n' + '=' * 60)
    print('测试 2: 样本登记与编号生成')
    print('-' * 60)

    success, no1 = sm.add_sample('血液', '张三', '2024-01-15', '冰箱A-01', '李医生')
    assert success, f'添加样本失败: {no1}'
    assert no1.startswith('BL'), f'编号前缀错误: {no1}'
    print(f'[OK] 样本1登记成功: {no1}')

    success, no2 = sm.add_sample('血液', '李四', '2024-01-16', '冰箱A-02', '李医生')
    assert success, f'添加样本失败: {no2}'
    assert no1 != no2, '编号重复!'
    print(f'[OK] 样本2登记成功: {no2}')

    success, no3 = sm.add_sample('尿液', '王五', '2024-01-17', '冰箱B-01', '王医生')
    assert success, f'添加样本失败: {no3}'
    assert no3.startswith('UR'), f'尿液样本编号前缀错误: {no3}'
    print(f'[OK] 样本3登记成功: {no3}')

    success, no4 = sm.add_sample('组织', '赵六', '2024-02-10', '冰箱C-01', '张医生', '冷冻切片')
    assert success, f'添加样本失败: {no4}'
    assert no4.startswith('TS'), f'组织样本编号前缀错误: {no4}'
    print(f'[OK] 样本4(带备注)登记成功: {no4}')

    sample = sm.get_sample_by_no(no1)
    assert sample is not None, '查询样本失败'
    assert sample['sample_type'] == '血液'
    assert sample['source'] == '张三'
    assert sample['status'] == sm.STATUS_AVAILABLE
    print(f'[OK] 样本查询验证通过')

    return no1, no2, no3, no4


def test_sample_no_uniqueness():
    print('\n' + '=' * 60)
    print('测试 3: 编号唯一性验证')
    print('-' * 60)

    conn = sqlite3.connect(sm.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sample_no FROM samples")
    all_nos = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert len(all_nos) == len(set(all_nos)), '存在重复的样本编号!'
    print(f'[OK] 所有 {len(all_nos)} 个样本编号均唯一')

    now = datetime.datetime.now()
    year_month = now.strftime('%Y%m')

    type_codes = set()
    for no in all_nos:
        type_code = no[:2]
        seq_part = no[2 + len(year_month):]
        assert len(seq_part) == 4, f'序号部分长度不对: {no}'
        assert seq_part.isdigit(), f'序号部分不是数字: {no}'
        type_codes.add(type_code)

    print(f'[OK] 编号格式验证通过')
    print(f'  涉及类型编码: {type_codes}')


def test_required_field_validation():
    print('\n' + '=' * 60)
    print('测试 4: 必填项校验')
    print('-' * 60)

    success, msg = sm.add_sample('', '来源', '2024-01-01', '位置', '负责人')
    assert not success, '样本类型为空应该添加失败'
    assert '不能为空' in msg, f'错误信息应包含"不能为空": {msg}'
    print(f'[OK] 样本类型为空校验通过: {msg}')

    success, msg = sm.add_sample(None, '来源', '2024-01-01', '位置', '负责人')
    assert not success, '样本类型为None应该添加失败'
    print(f'[OK] 样本类型为None校验通过')

    success, msg = sm.add_sample('血液', '', '2024-01-01', '位置', '负责人')
    assert not success, '样本来源为空应该添加失败'
    assert '不能为空' in msg, f'错误信息应包含"不能为空": {msg}'
    print(f'[OK] 样本来源为空校验通过: {msg}')

    success, msg = sm.add_sample('血液', '来源', '2024-01-01', '', '负责人')
    assert not success, '保存位置为空应该添加失败'
    assert '不能为空' in msg, f'错误信息应包含"不能为空": {msg}'
    print(f'[OK] 保存位置为空校验通过: {msg}')

    success, msg = sm.add_sample('血液', '来源', '2024-01-01', '位置', '')
    assert not success, '负责人为空应该添加失败'
    assert '不能为空' in msg, f'错误信息应包含"不能为空": {msg}'
    print(f'[OK] 负责人为空校验通过: {msg}')

    success, msg = sm.add_sample('血液', '   ', '2024-01-01', '位置', '负责人')
    assert not success, '样本来源为纯空格应该添加失败'
    print(f'[OK] 纯空格内容校验通过')

    success, msg = sm.add_sample('无效类型', '测试', '2024-01-01', '位置', '负责人')
    assert not success, '无效类型应该添加失败'
    print(f'[OK] 无效类型验证通过: {msg}')


def test_date_validation():
    print('\n' + '=' * 60)
    print('测试 5: 日期格式与范围校验')
    print('-' * 60)

    success, msg = sm.add_sample('血液', '测试', '', '位置', '负责人')
    assert not success, '采集日期为空应该添加失败'
    assert '不能为空' in msg, f'错误信息应包含"不能为空": {msg}'
    print(f'[OK] 采集日期为空校验通过: {msg}')

    success, msg = sm.add_sample('组织', '测试', '2024/01/01', '位置', '负责人')
    assert not success, '日期格式错误应该添加失败'
    assert 'YYYY-MM-DD' in msg, f'错误信息应包含格式提示: {msg}'
    print(f'[OK] 日期格式(斜杠)校验通过: {msg}')

    success, msg = sm.add_sample('组织', '测试', '2024-13-01', '位置', '负责人')
    assert not success, '无效月份应该添加失败'
    print(f'[OK] 无效月份校验通过: {msg}')

    success, msg = sm.add_sample('组织', '测试', '2024-02-30', '位置', '负责人')
    assert not success, '无效日期应该添加失败'
    print(f'[OK] 无效日期校验通过: {msg}')

    success, msg = sm.add_sample('组织', '测试', '01-01-2024', '位置', '负责人')
    assert not success, '颠倒日期格式应该添加失败'
    print(f'[OK] 颠倒日期格式校验通过: {msg}')

    future_date = (datetime.date.today() + datetime.timedelta(days=5)).strftime('%Y-%m-%d')
    success, msg = sm.add_sample('血液', '测试', future_date, '位置', '负责人')
    assert not success, '未来日期应该添加失败'
    assert '不能晚于当前日期' in msg, f'错误信息应包含日期范围提示: {msg}'
    print(f'[OK] 未来日期({future_date})校验通过: {msg}')

    today = datetime.date.today().strftime('%Y-%m-%d')
    success, no = sm.add_sample('血液', '今日采集', today, '位置', '负责人')
    assert success, f'今天的日期应该允许: {no}'
    print(f'[OK] 今天日期({today})校验通过: {no}')

    past_date = '2020-01-01'
    success, no = sm.add_sample('血液', '历史采集', past_date, '位置', '负责人')
    assert success, f'过去日期应该允许: {no}'
    print(f'[OK] 过去日期({past_date})校验通过: {no}')


def test_query_samples_basic(no1, no2, no3, no4):
    print('\n' + '=' * 60)
    print('测试 6: 基础样本查询功能')
    print('-' * 60)

    all_samples = sm.query_samples()
    assert len(all_samples) >= 4, '查询所有样本失败'
    print(f'[OK] 查询所有样本: {len(all_samples)} 条')

    blood_samples = sm.query_samples(sample_type='血液')
    assert len(blood_samples) >= 3, f'血液样本数量不对: {len(blood_samples)}'
    print(f'[OK] 按类型查询(血液): {len(blood_samples)} 条')

    urine_samples = sm.query_samples(sample_type='尿液')
    assert len(urine_samples) >= 1, f'尿液样本数量不对: {len(urine_samples)}'
    print(f'[OK] 按类型查询(尿液): {len(urine_samples)} 条')

    li_samples = sm.query_samples(manager='李')
    assert len(li_samples) >= 2, f'按负责人模糊查询失败: {len(li_samples)}'
    print(f'[OK] 按负责人模糊查询(李): {len(li_samples)} 条')

    fridge_a_samples = sm.query_samples(location='冰箱A')
    assert len(fridge_a_samples) >= 2, f'按位置模糊查询失败: {len(fridge_a_samples)}'
    print(f'[OK] 按位置模糊查询(冰箱A): {len(fridge_a_samples)} 条')

    available_samples = sm.query_samples(status=sm.STATUS_AVAILABLE)
    assert len(available_samples) >= 4, '在库样本查询失败'
    print(f'[OK] 按状态查询(在库): {len(available_samples)} 条')

    empty_result = sm.query_samples(manager='不存在的人')
    assert len(empty_result) == 0, '不存在的查询应该返回空'
    print(f'[OK] 空结果查询验证通过')


def test_query_combined(no1, no2, no3, no4):
    print('\n' + '=' * 60)
    print('测试 7: 组合条件查询')
    print('-' * 60)

    combo = sm.query_samples(sample_type='血液', manager='李')
    assert len(combo) >= 2, f'血液+李医生组合查询失败: {len(combo)}'
    for s in combo:
        assert s['sample_type'] == '血液'
        assert '李' in s['manager']
    print(f'[OK] 类型+负责人组合查询通过: {len(combo)} 条')

    combo2 = sm.query_samples(sample_type='血液', location='冰箱A', status=sm.STATUS_AVAILABLE)
    assert len(combo2) >= 2, f'多条件组合查询失败: {len(combo2)}'
    for s in combo2:
        assert s['sample_type'] == '血液'
        assert '冰箱A' in s['storage_location']
        assert s['status'] == sm.STATUS_AVAILABLE
    print(f'[OK] 类型+位置+状态组合查询通过: {len(combo2)} 条')

    combo3 = sm.query_samples(sample_type='尿液', manager='王')
    assert len(combo3) >= 1, f'尿液+王医生组合查询失败: {len(combo3)}'
    print(f'[OK] 尿液+王医生组合查询通过: {len(combo3)} 条')

    empty_combo = sm.query_samples(sample_type='血液', manager='不存在的人')
    assert len(empty_combo) == 0, '无匹配的组合查询应返回空'
    print(f'[OK] 无匹配组合查询验证通过')


def test_query_date_range():
    print('\n' + '=' * 60)
    print('测试 8: 采集日期范围查询')
    print('-' * 60)

    jan_samples = sm.query_samples(collect_date_start='2024-01-01', collect_date_end='2024-01-31')
    assert len(jan_samples) >= 3, f'一月份样本查询失败: {len(jan_samples)}'
    for s in jan_samples:
        assert '2024-01' in s['collect_date'], f'不在一月范围内: {s["collect_date"]}'
    print(f'[OK] 一月份范围查询通过: {len(jan_samples)} 条')

    feb_samples = sm.query_samples(collect_date_start='2024-02-01', collect_date_end='2024-02-28')
    assert len(feb_samples) >= 1, f'二月份样本查询失败: {len(feb_samples)}'
    for s in feb_samples:
        assert '2024-02' in s['collect_date'], f'不在二月范围内: {s["collect_date"]}'
    print(f'[OK] 二月份范围查询通过: {len(feb_samples)} 条')

    start_only = sm.query_samples(collect_date_start='2024-02-01')
    assert len(start_only) >= 1, '仅指定起始日期查询失败'
    print(f'[OK] 仅指定起始日期查询通过: {len(start_only)} 条')

    end_only = sm.query_samples(collect_date_end='2024-01-31')
    assert len(end_only) >= 3, '仅指定结束日期查询失败'
    print(f'[OK] 仅指定结束日期查询通过: {len(end_only)} 条')

    no_result_range = sm.query_samples(collect_date_start='2025-01-01', collect_date_end='2025-12-31')
    assert len(no_result_range) == 0, '无匹配日期范围应返回空'
    print(f'[OK] 无匹配日期范围验证通过')

    combined = sm.query_samples(
        sample_type='血液',
        collect_date_start='2024-01-01',
        collect_date_end='2024-01-31'
    )
    assert len(combined) >= 2, f'类型+日期范围组合查询失败: {len(combined)}'
    for s in combined:
        assert s['sample_type'] == '血液'
        assert '2024-01' in s['collect_date']
    print(f'[OK] 类型+日期范围组合查询通过: {len(combined)} 条')


def test_query_sorting(no1, no2, no3, no4):
    print('\n' + '=' * 60)
    print('测试 9: 查询结果排序')
    print('-' * 60)

    desc_created = sm.query_samples(sort_by=sm.SORT_CREATED_DESC)
    assert len(desc_created) >= 4
    for i in range(len(desc_created) - 1):
        assert desc_created[i]['created_at'] >= desc_created[i + 1]['created_at'], \
            f'按登记时间降序排列错误: {desc_created[i]["created_at"]} < {desc_created[i+1]["created_at"]}'
    print('[OK] 按登记时间降序排列验证通过')

    asc_created = sm.query_samples(sort_by=sm.SORT_CREATED_ASC)
    assert len(asc_created) >= 4
    for i in range(len(asc_created) - 1):
        assert asc_created[i]['created_at'] <= asc_created[i + 1]['created_at'], \
            f'按登记时间升序排列错误'
    print('[OK] 按登记时间升序排列验证通过')

    desc_collect = sm.query_samples(sort_by=sm.SORT_COLLECT_DESC)
    assert len(desc_collect) >= 4
    for i in range(len(desc_collect) - 1):
        assert desc_collect[i]['collect_date'] >= desc_collect[i + 1]['collect_date'], \
            f'按采集日期降序排列错误'
    print('[OK] 按采集日期降序排列验证通过')

    asc_collect = sm.query_samples(sort_by=sm.SORT_COLLECT_ASC)
    assert len(asc_collect) >= 4
    for i in range(len(asc_collect) - 1):
        assert asc_collect[i]['collect_date'] <= asc_collect[i + 1]['collect_date'], \
            f'按采集日期升序排列错误'
    print('[OK] 按采集日期升序排列验证通过')

    default_sort = sm.query_samples()
    assert len(default_sort) >= 4
    for i in range(len(default_sort) - 1):
        assert default_sort[i]['created_at'] >= default_sort[i + 1]['created_at'], \
            f'默认排序(登记时间降序)错误'
    print('[OK] 默认排序(登记时间降序)验证通过')


def test_borrow_basic(no1, no2):
    print('\n' + '=' * 60)
    print('测试 10: 样本借出基础流程')
    print('-' * 60)

    success, msg = sm.borrow_sample(no1, '赵研究员', 'PCR实验')
    assert success, f'借出失败: {msg}'
    print(f'[OK] 样本借出成功: {no1}')

    sample = sm.get_sample_by_no(no1)
    assert sample['status'] == sm.STATUS_BORROWED, '借出后状态未更新'
    print(f'[OK] 借出后状态验证: {sample["status"]}')

    records = sm.get_borrow_records(no1)
    assert len(records) >= 1, '借出记录未创建'
    assert records[0]['borrower'] == '赵研究员', '借用人信息错误'
    assert records[0]['purpose'] == 'PCR实验', '用途信息错误'
    assert records[0]['status'] == '借出中', '记录状态应为借出中'
    assert records[0]['return_date'] is None, '借出中不应有归还时间'
    print('[OK] 借出记录详情验证通过')

    borrowed_samples = sm.query_samples(status=sm.STATUS_BORROWED)
    assert len(borrowed_samples) >= 1, '借出状态查询失败'
    assert any(s['sample_no'] == no1 for s in borrowed_samples), '借出样本不在借出列表中'
    print(f'[OK] 借出状态查询验证通过: {len(borrowed_samples)} 条')


def test_borrow_validation():
    print('\n' + '=' * 60)
    print('测试 11: 借出参数校验')
    print('-' * 60)

    success, no = sm.add_sample('血液', '测试借出校验', '2024-03-01', '冰箱D-01', '李医生')
    assert success, f'准备测试样本失败: {no}'

    success, msg = sm.borrow_sample('', '借用人', '用途')
    assert not success, '空样本编号应借出失败'
    assert '不能为空' in msg, f'错误信息应包含提示: {msg}'
    print(f'[OK] 空样本编号校验通过: {msg}')

    success, msg = sm.borrow_sample(no, '', '用途')
    assert not success, '空借用人应借出失败'
    assert '不能为空' in msg, f'错误信息应包含提示: {msg}'
    print(f'[OK] 空借用人校验通过: {msg}')

    success, msg = sm.borrow_sample(no, '借用人', '')
    assert not success, '空用途应借出失败'
    assert '不能为空' in msg, f'错误信息应包含提示: {msg}'
    print(f'[OK] 空用途校验通过: {msg}')

    success, msg = sm.borrow_sample(no, '   ', '用途')
    assert not success, '纯空格借用人应借出失败'
    print(f'[OK] 纯空格借用人校验通过')

    success, msg = sm.borrow_sample('NOTEXIST', '借用人', '用途')
    assert not success, '不存在的样本不应能借出'
    print(f'[OK] 不存在样本借出校验通过')

    return no


def test_duplicate_borrow(no1):
    print('\n' + '=' * 60)
    print('测试 12: 重复借出拦截')
    print('-' * 60)

    sample = sm.get_sample_by_no(no1)
    assert sample['status'] == sm.STATUS_BORROWED, '测试前提: 样本应已借出'

    success, msg = sm.borrow_sample(no1, '孙研究员', '另一个实验')
    assert not success, '已借出样本不应能重复借出'
    assert '已被借出' in msg or '无法重复借出' in msg, f'错误信息应提示已借出: {msg}'
    print(f'[OK] 重复借出拦截通过: {msg}')

    sample_after = sm.get_sample_by_no(no1)
    assert sample_after['status'] == sm.STATUS_BORROWED, '重复借出不应改变状态'
    records = sm.get_borrow_records(no1)
    active = [r for r in records if r['status'] == '借出中']
    assert len(active) == 1, '重复借出不应创建多条借出中记录'
    print('[OK] 重复借出未影响现有状态验证通过')


def test_return_basic(no1):
    print('\n' + '=' * 60)
    print('测试 13: 样本归还基础流程')
    print('-' * 60)

    sample = sm.get_sample_by_no(no1)
    assert sample['status'] == sm.STATUS_BORROWED, '测试前提: 样本应已借出'

    success, msg = sm.return_sample(no1)
    assert success, f'归还失败: {msg}'
    print(f'[OK] 样本归还成功: {no1}')

    sample_after = sm.get_sample_by_no(no1)
    assert sample_after['status'] == sm.STATUS_AVAILABLE, '归还后状态未更新'
    print(f'[OK] 归还后状态验证: {sample_after["status"]}')

    records = sm.get_borrow_records(no1)
    latest = records[0]
    assert latest['status'] == '已归还', '记录状态应为已归还'
    assert latest['return_date'] is not None, '应有归还时间'
    assert latest['borrower'] == '赵研究员', '借用人信息不应改变'
    assert latest['purpose'] == 'PCR实验', '用途信息不应改变'
    print('[OK] 归还记录详情验证通过')


def test_return_validation():
    print('\n' + '=' * 60)
    print('测试 14: 归还参数与状态校验')
    print('-' * 60)

    success, no = sm.add_sample('血液', '测试归还校验', '2024-03-02', '冰箱D-02', '王医生')
    assert success, f'准备测试样本失败: {no}'

    success, msg = sm.return_sample('')
    assert not success, '空样本编号应归还失败'
    assert '不能为空' in msg, f'错误信息应包含提示: {msg}'
    print(f'[OK] 空样本编号校验通过: {msg}')

    success, msg = sm.return_sample('NOTEXIST')
    assert not success, '不存在的样本不应能归还'
    print(f'[OK] 不存在样本归还校验通过')

    success, msg = sm.return_sample(no)
    assert not success, '已在库样本不应能归还'
    assert '已在库' in msg or '无需归还' in msg, f'错误信息应提示已在库: {msg}'
    print(f'[OK] 已在库样本归还校验通过: {msg}')

    return no


def test_duplicate_return(no1):
    print('\n' + '=' * 60)
    print('测试 15: 重复归还拦截')
    print('-' * 60)

    sample = sm.get_sample_by_no(no1)
    assert sample['status'] == sm.STATUS_AVAILABLE, '测试前提: 样本应已在库'

    success, msg = sm.return_sample(no1)
    assert not success, '已归还样本不应能重复归还'
    assert '已在库' in msg or '无需归还' in msg, f'错误信息应提示已在库: {msg}'
    print(f'[OK] 重复归还拦截通过: {msg}')

    sample_after = sm.get_sample_by_no(no1)
    assert sample_after['status'] == sm.STATUS_AVAILABLE, '重复归还不应改变状态'
    print('[OK] 重复归还未影响状态验证通过')


def test_borrow_records_query(no1, no2):
    print('\n' + '=' * 60)
    print('测试 16: 借还记录查询')
    print('-' * 60)

    all_records = sm.get_borrow_records()
    assert len(all_records) >= 1, '借还记录查询失败'
    print(f'[OK] 查询所有借还记录(初始): {len(all_records)} 条')

    no1_records = sm.get_borrow_records(no1)
    assert len(no1_records) >= 1, f'样本 {no1} 的借还记录查询失败'
    assert no1_records[0]['status'] == '已归还'
    assert no1_records[0]['return_date'] is not None
    print(f'[OK] 按样本编号查询已归还记录 ({no1}): {len(no1_records)} 条')

    sm.borrow_sample(no2, '钱研究员', '测序实验')
    no2_records = sm.get_borrow_records(no2)
    assert len(no2_records) >= 1
    assert no2_records[0]['status'] == '借出中'
    assert no2_records[0]['return_date'] is None
    print(f'[OK] 按样本编号查询借出中记录 ({no2}): {len(no2_records)} 条')

    all_records_after = sm.get_borrow_records()
    assert len(all_records_after) >= 2, '借还记录数量应 >= 2'
    print(f'[OK] 查询所有借还记录(新增后): {len(all_records_after)} 条')

    empty_records = sm.get_borrow_records('NOTEXIST')
    assert len(empty_records) == 0
    print('[OK] 不存在样本的记录查询验证通过')


def test_borrow_return_full_cycle():
    print('\n' + '=' * 60)
    print('测试 17: 完整借还生命周期')
    print('-' * 60)

    success, no = sm.add_sample('唾液', '生命周期测试', '2024-04-01', '冰箱E-01', '周医生')
    assert success, f'创建测试样本失败: {no}'
    print(f'[OK] 创建测试样本: {no}')

    sample = sm.get_sample_by_no(no)
    assert sample['status'] == sm.STATUS_AVAILABLE
    print('[OK] 初始状态为在库')

    success, msg = sm.borrow_sample(no, '吴研究员', 'ELISA检测')
    assert success, f'首次借出失败: {msg}'
    sample = sm.get_sample_by_no(no)
    assert sample['status'] == sm.STATUS_BORROWED
    print('[OK] 首次借出后状态为借出')

    success, msg = sm.borrow_sample(no, '郑研究员', '其他实验')
    assert not success, '借出中不应能重复借出'
    print('[OK] 借出中拦截重复借出')

    success, msg = sm.return_sample(no)
    assert success, f'首次归还失败: {msg}'
    sample = sm.get_sample_by_no(no)
    assert sample['status'] == sm.STATUS_AVAILABLE
    print('[OK] 首次归还后状态为在库')

    success, msg = sm.return_sample(no)
    assert not success, '已归还不应能重复归还'
    print('[OK] 在库中拦截重复归还')

    success, msg = sm.borrow_sample(no, '冯研究员', '质谱分析')
    assert success, f'再次借出失败: {msg}'
    sample = sm.get_sample_by_no(no)
    assert sample['status'] == sm.STATUS_BORROWED
    print('[OK] 再次借出成功')

    records = sm.get_borrow_records(no)
    assert len(records) == 2, f'应有2条借还记录: {len(records)}'
    print(f'[OK] 累计借还记录: {len(records)} 条')

    success, msg = sm.return_sample(no)
    assert success, f'再次归还失败: {msg}'
    sample = sm.get_sample_by_no(no)
    assert sample['status'] == sm.STATUS_AVAILABLE
    print('[OK] 再次归还成功，生命周期完整')


def test_db_path_config():
    print('\n' + '=' * 60)
    print('测试 18: 数据库路径配置')
    print('-' * 60)

    original_path = sm.DB_PATH
    test_dir = os.path.dirname(os.path.abspath(__file__))

    sm.set_db_path('custom_test.db')
    expected = os.path.join(test_dir, 'custom_test.db')
    assert sm.DB_PATH == expected, f'set_db_path 相对路径错误: {sm.DB_PATH} != {expected}'
    print('[OK] set_db_path 相对路径解析通过')

    abs_path = os.path.join(test_dir, 'abs_test.db')
    sm.set_db_path(abs_path)
    assert sm.DB_PATH == abs_path, f'set_db_path 绝对路径错误: {sm.DB_PATH} != {abs_path}'
    print('[OK] set_db_path 绝对路径设置通过')

    sm.set_db_path(original_path)
    print(f'[OK] 数据库路径恢复: {sm.DB_PATH}')

    custom_files = ['custom_test.db', 'abs_test.db']
    for f in custom_files:
        full = os.path.join(test_dir, f)
        if os.path.exists(full):
            os.remove(full)


def run_all_tests():
    print('\n' + '#' * 60)
    print('#  实验室样本管理系统 - 完整功能测试')
    print('#' * 60)

    test_db = setup_test_db()
    print(f'测试数据库路径: {test_db}')

    try:
        test_init()
        no1, no2, no3, no4 = test_add_sample_basic()
        test_sample_no_uniqueness()
        test_required_field_validation()
        test_date_validation()
        test_query_samples_basic(no1, no2, no3, no4)
        test_query_combined(no1, no2, no3, no4)
        test_query_date_range()
        test_query_sorting(no1, no2, no3, no4)
        test_borrow_basic(no1, no2)
        test_borrow_validation()
        test_duplicate_borrow(no1)
        test_return_basic(no1)
        test_return_validation()
        test_duplicate_return(no1)
        test_borrow_records_query(no1, no2)
        test_borrow_return_full_cycle()
        test_db_path_config()

        print('\n' + '#' * 60)
        print('#  [OK] 所有 18 项测试全部通过！')
        print('#' * 60)
        return True

    except AssertionError as e:
        print(f'\n[FAIL] 测试断言失败: {e}')
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f'\n[FAIL] 发生异常: {e}')
        import traceback
        traceback.print_exc()
        return False
    finally:
        cleanup_test_db(test_db)
        if not os.path.exists(test_db):
            print(f'\n[OK] 测试数据库已清理: {test_db}')
        else:
            print(f'\n[WARN] 测试数据库未完全清理: {test_db}')


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
