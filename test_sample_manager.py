import os
import sys
import sqlite3
import tempfile
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sample_manager as sm


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


def test_add_sample():
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

    sample = sm.get_sample_by_no(no1)
    assert sample is not None, '查询样本失败'
    assert sample['sample_type'] == '血液'
    assert sample['source'] == '张三'
    assert sample['status'] == sm.STATUS_AVAILABLE
    print(f'[OK] 样本查询验证通过')

    success, msg = sm.add_sample('无效类型', '测试', '2024-01-01', '位置', '负责人')
    assert not success, '无效类型应该添加失败'
    print(f'[OK] 无效类型验证通过: {msg}')

    success, msg = sm.add_sample('组织', '测试', '2024/01/01', '位置', '负责人')
    assert not success, '日期格式错误应该添加失败'
    print(f'[OK] 日期格式验证通过: {msg}')

    return no1, no2, no3


def test_query_samples(no1, no2, no3):
    print('\n' + '=' * 60)
    print('测试 3: 样本查询功能')
    print('-' * 60)

    all_samples = sm.query_samples()
    assert len(all_samples) >= 3, '查询所有样本失败'
    print(f'[OK] 查询所有样本: {len(all_samples)} 条')

    blood_samples = sm.query_samples(sample_type='血液')
    assert len(blood_samples) == 2, f'血液样本数量不对: {len(blood_samples)}'
    print(f'[OK] 按类型查询(血液): {len(blood_samples)} 条')

    li_samples = sm.query_samples(manager='李')
    assert len(li_samples) >= 2, f'按负责人模糊查询失败: {len(li_samples)}'
    print(f'[OK] 按负责人模糊查询(李): {len(li_samples)} 条')

    fridge_a_samples = sm.query_samples(location='冰箱A')
    assert len(fridge_a_samples) >= 2, f'按位置模糊查询失败: {len(fridge_a_samples)}'
    print(f'[OK] 按位置模糊查询(冰箱A): {len(fridge_a_samples)} 条')

    available_samples = sm.query_samples(status=sm.STATUS_AVAILABLE)
    assert len(available_samples) >= 3, '在库样本查询失败'
    print(f'[OK] 按状态查询(在库): {len(available_samples)} 条')

    empty_result = sm.query_samples(manager='不存在的人')
    assert len(empty_result) == 0, '不存在的查询应该返回空'
    print(f'[OK] 空结果查询验证通过')

    combo = sm.query_samples(sample_type='血液', manager='李')
    assert len(combo) >= 2, '组合查询失败'
    print(f'[OK] 组合查询验证通过')


def test_borrow_return(no1, no2):
    print('\n' + '=' * 60)
    print('测试 4: 借还状态流转')
    print('-' * 60)

    success, msg = sm.borrow_sample(no1, '赵研究员', 'PCR实验')
    assert success, f'借出失败: {msg}'
    print(f'[OK] 样本借出成功: {no1}')

    sample = sm.get_sample_by_no(no1)
    assert sample['status'] == sm.STATUS_BORROWED, '借出后状态未更新'
    print(f'[OK] 借出后状态验证: {sample["status"]}')

    success, msg = sm.borrow_sample(no1, '孙研究员', '另一个实验')
    assert not success, '已借出样本不应能重复借出'
    print(f'[OK] 重复借出验证通过: {msg}')

    success, msg = sm.borrow_sample('NOTEXIST', '测试', '测试')
    assert not success, '不存在的样本不应能借出'
    print(f'[OK] 不存在样本借出验证通过')

    success, msg = sm.return_sample(no1)
    assert success, f'归还失败: {msg}'
    print(f'[OK] 样本归还成功: {no1}')

    sample = sm.get_sample_by_no(no1)
    assert sample['status'] == sm.STATUS_AVAILABLE, '归还后状态未更新'
    print(f'[OK] 归还后状态验证: {sample["status"]}')

    success, msg = sm.return_sample(no1)
    assert not success, '已在库样本不应能归还'
    print(f'[OK] 重复归还验证通过: {msg}')

    success, msg = sm.return_sample('NOTEXIST')
    assert not success, '不存在的样本不应能归还'
    print(f'[OK] 不存在样本归还验证通过')

    sm.borrow_sample(no2, '钱研究员', '测序')
    print(f'  借出样本 {no2} 用于后续记录测试')


def test_borrow_records(no1, no2):
    print('\n' + '=' * 60)
    print('测试 5: 借还记录管理')
    print('-' * 60)

    all_records = sm.get_borrow_records()
    assert len(all_records) >= 2, '借还记录查询失败'
    print(f'[OK] 查询所有借还记录: {len(all_records)} 条')

    no1_records = sm.get_borrow_records(no1)
    assert len(no1_records) >= 1, f'样本 {no1} 的借还记录查询失败'
    print(f'[OK] 按样本编号查询记录 ({no1}): {len(no1_records)} 条')

    assert no1_records[0]['borrower'] == '赵研究员', '借用人信息错误'
    assert no1_records[0]['purpose'] == 'PCR实验', '用途信息错误'
    assert no1_records[0]['status'] == '已归还', '记录状态应为已归还'
    assert no1_records[0]['return_date'] is not None, '应有归还时间'
    print(f'[OK] 借还记录详情验证通过')

    no2_records = sm.get_borrow_records(no2)
    assert len(no2_records) >= 1
    assert no2_records[0]['status'] == '借出中', '记录状态应为借出中'
    assert no2_records[0]['return_date'] is None, '借出中不应有归还时间'
    print(f'[OK] 借出中记录状态验证通过')

    empty_records = sm.get_borrow_records('NOTEXIST')
    assert len(empty_records) == 0
    print(f'[OK] 不存在样本的记录查询验证通过')


def test_sample_no_uniqueness():
    print('\n' + '=' * 60)
    print('测试 6: 编号唯一性验证')
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


def run_all_tests():
    print('\n' + '#' * 60)
    print('#  实验室样本管理系统 - 功能测试')
    print('#' * 60)

    test_db = os.path.join(os.path.dirname(sm.DB_PATH), 'test_samples.db')
    sm.DB_PATH = test_db

    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        test_init()
        no1, no2, no3 = test_add_sample()
        test_query_samples(no1, no2, no3)
        test_borrow_return(no1, no2)
        test_borrow_records(no1, no2)
        test_sample_no_uniqueness()

        print('\n' + '#' * 60)
        print('#  [OK] 所有测试通过！')
        print('#' * 60)

    except AssertionError as e:
        print(f'\n[FAIL] 测试失败: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n[FAIL] 发生异常: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


if __name__ == '__main__':
    run_all_tests()
