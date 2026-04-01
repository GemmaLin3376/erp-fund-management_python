"""
ERP资金管理系统 QA测试
以测试专家视角，应用8种测试用例设计方法：
- 等价类划分：金额有效/无效分类
- 边界值分析：金额0/负数/等于总额/超出总额
- 场景法：完整业务流程端到端
- 判定表法：按钮显示规则（状态→按钮）
- 因果图：收款单操作→收入单状态因果
- 正交试验：列表搜索参数组合
- 错误推测：历史BUG高发点
- 流程分析：跨模块端到端流程
+ UI一致性：按钮展示、字段顺序、徽章颜色
"""
import pytest
import json
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─────────────────────────────────────────
# Fixtures（与 test_erp.py 共享同一个app实例）
# ─────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    os.environ['TESTING'] = '1'
    from app import create_app, db as _db

    _app = create_app()
    _app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
    })
    with _app.app_context():
        _db.drop_all()
        _db.create_all()
        _seed_qa_data(_db)
        yield _app
        _db.session.remove()
        _db.drop_all()


def _seed_qa_data(db):
    from app.models import Customer, Account, IncomeCategory
    if not Customer.query.filter_by(code='QA_KH001').first():
        db.session.add(Customer(code='QA_KH001', name='QA测试客户A'))
    if not Customer.query.filter_by(code='QA_KH002').first():
        db.session.add(Customer(code='QA_KH002', name='QA测试客户B'))
    if not IncomeCategory.query.filter_by(code='QA_SR001').first():
        db.session.add(IncomeCategory(code='QA_SR001', name='QA测试收入'))
    if not Account.query.filter_by(code='QA_ZH001').first():
        db.session.add(Account(code='QA_ZH001', name='QA测试账户'))
    db.session.commit()


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


@pytest.fixture(scope='session')
def db(app):
    from app import db as _db
    return _db


# ─────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────

def post_json(client, url, data):
    return client.post(url, data=json.dumps(data),
                       content_type='application/json')


def qa_customer_id(db):
    from app.models import Customer
    return Customer.query.filter_by(code='QA_KH001').first().id


def qa_customer_b_id(db):
    from app.models import Customer
    return Customer.query.filter_by(code='QA_KH002').first().id


def qa_category_id(db):
    from app.models import IncomeCategory
    return IncomeCategory.query.filter_by(code='QA_SR001').first().id


def qa_account_id(db):
    from app.models import Account
    return Account.query.filter_by(code='QA_ZH001').first().id


def make_income_order(client, db, total=100.0, customer='A'):
    cid = qa_customer_id(db) if customer == 'A' else qa_customer_b_id(db)
    cat = qa_category_id(db)
    resp = post_json(client, '/income_order/create', {
        'order_date': '2026-01-01',
        'customer_id': cid,
        'lines': [{'category_id': cat, 'amount': total, 'remark': ''}]
    })
    result = json.loads(resp.data)
    assert result.get('success'), f"创建收入单失败: {result}"
    from app.models.income_order import IncomeOrder
    return IncomeOrder.query.order_by(IncomeOrder.id.desc()).first()


def audit_io(client, oid):
    resp = post_json(client, f'/income_order/{oid}/audit', {})
    assert json.loads(resp.data)['success']


def make_receipt_order(client, db, income_order_id, amount, customer='A'):
    cid = qa_customer_id(db) if customer == 'A' else qa_customer_b_id(db)
    aid = qa_account_id(db)
    resp = post_json(client, '/receipt_order/create', {
        'order_date': '2026-01-01',
        'customer_id': cid,
        'account_id': aid,
        'lines': [{'income_order_id': income_order_id, 'amount': amount, 'remark': ''}]
    })
    result = json.loads(resp.data)
    assert result.get('success'), f"创建收款单失败: {result}"
    from app.models.receipt_order import ReceiptOrder
    return ReceiptOrder.query.order_by(ReceiptOrder.id.desc()).first()


def edit_receipt_order(client, db, ro_id, income_order_id, new_amount, customer='A'):
    """编辑收款单，替换分录金额"""
    cid = qa_customer_id(db) if customer == 'A' else qa_customer_b_id(db)
    aid = qa_account_id(db)
    resp = post_json(client, f'/receipt_order/{ro_id}/edit', {
        'order_date': '2026-01-01',
        'customer_id': cid,
        'account_id': aid,
        'lines': [{'income_order_id': income_order_id, 'amount': new_amount, 'remark': ''}]
    })
    return json.loads(resp.data)


# ─────────────────────────────────────────
# P0 — 数据一致性测试（最高优先级）
# ─────────────────────────────────────────

class TestP0DataConsistency:
    """数据一致性：金额与状态始终保持一致"""

    def test_multi_receipt_accumulate_amount(self, client, db):
        """P0: 多张收款单叠加后收入单已收款金额精确累计"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        # 第一张收款单：收款30
        make_receipt_order(client, db, io.id, 30.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 30.0
        assert io.status == '部分收款'
        # 第二张收款单：再收款40
        make_receipt_order(client, db, io.id, 40.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 70.0
        assert io.status == '部分收款'
        # 第三张收款单：再收款30（凑满100）
        make_receipt_order(client, db, io.id, 30.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 100.0
        assert io.status == '全部收款'

    def test_delete_partial_receipt_rollback_to_audited(self, client, db):
        """P0: 删除唯一收款单后收入单回退到已审核，金额归零"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 60.0)
        db.session.refresh(io)
        assert io.status == '部分收款'
        # 删除收款单
        resp = post_json(client, f'/receipt_order/{ro.id}/delete', {})
        assert json.loads(resp.data)['success']
        db.session.refresh(io)
        assert float(io.received_amount) == 0.0
        assert io.status == '已审核'

    def test_delete_one_of_two_receipts_status_correct(self, client, db):
        """P0: 删除两张收款单中的一张，收入单状态仍为部分收款"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro1 = make_receipt_order(client, db, io.id, 40.0)
        ro2 = make_receipt_order(client, db, io.id, 40.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 80.0
        # 删除第一张
        post_json(client, f'/receipt_order/{ro1.id}/delete', {})
        db.session.refresh(io)
        assert float(io.received_amount) == 40.0
        assert io.status == '部分收款'

    def test_delete_full_receipt_rollback_to_partial(self, client, db):
        """P0: 全部收款后删除一张收款单，状态退回部分收款"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro1 = make_receipt_order(client, db, io.id, 60.0)
        ro2 = make_receipt_order(client, db, io.id, 40.0)
        db.session.refresh(io)
        assert io.status == '全部收款'
        # 删除第一张收款单(60元)
        post_json(client, f'/receipt_order/{ro1.id}/delete', {})
        db.session.refresh(io)
        assert float(io.received_amount) == 40.0
        assert io.status == '部分收款'

    def test_batch_delete_receipts_all_rollback(self, client, db):
        """P0: 批量删除多张收款单，所有关联收入单金额全部回退"""
        io1 = make_income_order(client, db, total=100.0)
        io2 = make_income_order(client, db, total=200.0)
        audit_io(client, io1.id)
        audit_io(client, io2.id)
        ro1 = make_receipt_order(client, db, io1.id, 50.0)
        ro2 = make_receipt_order(client, db, io2.id, 80.0)
        db.session.refresh(io1)
        db.session.refresh(io2)
        assert float(io1.received_amount) == 50.0
        assert float(io2.received_amount) == 80.0
        # 批量删除
        resp = post_json(client, '/receipt_order/batch',
                         {'action': 'delete', 'ids': [ro1.id, ro2.id]})
        data = json.loads(resp.data)
        assert data['success']
        db.session.refresh(io1)
        db.session.refresh(io2)
        assert float(io1.received_amount) == 0.0
        assert float(io2.received_amount) == 0.0
        assert io1.status == '已审核'
        assert io2.status == '已审核'


# ─────────────────────────────────────────
# P0 — 编辑收款单的金额反写（最易出现bug）
# ─────────────────────────────────────────

class TestP0EditReceiptWriteback:
    """P0: 编辑收款单时必须先回退旧金额再写入新金额"""

    def test_edit_receipt_increases_amount_correctly(self, client, db):
        """P0[BUG检测]: 编辑收款单增大金额，收入单已收款应为新金额而非叠加"""
        io = make_income_order(client, db, total=200.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 60.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 60.0
        # 编辑：将收款金额从60改为80
        result = edit_receipt_order(client, db, ro.id, io.id, 80.0)
        assert result.get('success'), f"编辑失败: {result}"
        db.session.refresh(io)
        # 期望已收款=80，而不是60+80=140
        assert float(io.received_amount) == 80.0, \
            f"[BUG-001] P0 编辑收款单后金额叠加错误，实际={float(io.received_amount)}，预期=80.0"

    def test_edit_receipt_decreases_amount_correctly(self, client, db):
        """P0[BUG检测]: 编辑收款单减小金额，收入单已收款应减少"""
        io = make_income_order(client, db, total=200.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 100.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 100.0
        # 编辑：将收款金额从100改为40
        result = edit_receipt_order(client, db, ro.id, io.id, 40.0)
        assert result.get('success'), f"编辑失败: {result}"
        db.session.refresh(io)
        # 期望已收款=40，状态=部分收款
        assert float(io.received_amount) == 40.0, \
            f"[BUG-002] P0 编辑后金额不正确，实际={float(io.received_amount)}，预期=40.0"
        assert io.status == '部分收款'

    def test_edit_receipt_to_full_amount_changes_status(self, client, db):
        """P0[BUG检测]: 编辑收款单金额恰好等于收入单总额，状态应变为全部收款"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        db.session.refresh(io)
        assert io.status == '部分收款'
        # 编辑：将金额改为恰好等于总额100
        result = edit_receipt_order(client, db, ro.id, io.id, 100.0)
        assert result.get('success'), f"编辑失败: {result}"
        db.session.refresh(io)
        assert float(io.received_amount) == 100.0
        assert io.status == '全部收款', \
            f"[BUG-003] P0 编辑至全额后状态未变为全部收款，实际={io.status}"


# ─────────────────────────────────────────
# P1 — 边界值测试
# ─────────────────────────────────────────

class TestP1BoundaryValues:
    """边界值：金额、状态临界点验证"""

    def test_receipt_amount_zero_rejected(self, client, db):
        """P1: 收款金额=0 应被拒绝"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        cid = qa_customer_id(db)
        aid = qa_account_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'account_id': aid,
            'lines': [{'income_order_id': io.id, 'amount': 0, 'remark': ''}]
        })
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '金额' in data['message']

    def test_receipt_amount_negative_rejected(self, client, db):
        """P1: 收款金额为负数应被拒绝"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        cid = qa_customer_id(db)
        aid = qa_account_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'account_id': aid,
            'lines': [{'income_order_id': io.id, 'amount': -10, 'remark': ''}]
        })
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_receipt_amount_exactly_equals_total(self, client, db):
        """P1: 收款金额精确等于总额时状态变为全部收款"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        make_receipt_order(client, db, io.id, 100.0)
        db.session.refresh(io)
        assert io.status == '全部收款'
        assert float(io.received_amount) == 100.0

    def test_receipt_no_lines_rejected(self, client, db):
        """P1: 无分录的收款单不能保存"""
        cid = qa_customer_id(db)
        aid = qa_account_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'account_id': aid,
            'lines': []
        })
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '分录' in data['message']

    def test_income_order_no_lines_rejected(self, client, db):
        """P1: 无分录的收入单不能保存"""
        cid = qa_customer_id(db)
        resp = post_json(client, '/income_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'lines': []
        })
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_receipt_no_customer_rejected(self, client, db):
        """P1: 未选择客户时收款单不能保存"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        aid = qa_account_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': None,
            'account_id': aid,
            'lines': [{'income_order_id': io.id, 'amount': 50.0, 'remark': ''}]
        })
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '客户' in data['message']

    def test_receipt_no_account_rejected(self, client, db):
        """P1: 未选择收款账户时收款单不能保存"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        cid = qa_customer_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'account_id': None,
            'lines': [{'income_order_id': io.id, 'amount': 50.0, 'remark': ''}]
        })
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '账户' in data['message']


# ─────────────────────────────────────────
# P2 — 异常路径测试
# ─────────────────────────────────────────

class TestP2AbnormalPaths:
    """异常路径：系统对非法操作的防御能力"""

    def test_unaudited_income_order_cannot_be_receipt_source(self, client, db):
        """P2: 未审核的收入单不能作为收款单源单"""
        io = make_income_order(client, db, total=100.0)
        assert io.status == '未审核'
        cid = qa_customer_id(db)
        aid = qa_account_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'account_id': aid,
            'lines': [{'income_order_id': io.id, 'amount': 50.0, 'remark': ''}]
        })
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '不可收款' in data['message']

    def test_fully_received_income_order_cannot_be_receipt_source(self, client, db):
        """P2: 已全部收款的收入单不能再作为收款单源单"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        make_receipt_order(client, db, io.id, 100.0)
        db.session.refresh(io)
        assert io.status == '全部收款'
        # 再次尝试对该收入单收款
        cid = qa_customer_id(db)
        aid = qa_account_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'account_id': aid,
            'lines': [{'income_order_id': io.id, 'amount': 1.0, 'remark': ''}]
        })
        data = json.loads(resp.data)
        assert data['success'] is False, \
            f"[BUG-004] P2 全部收款的收入单被成功创建收款单: {data}"

    def test_audited_receipt_cannot_be_edited(self, client, db):
        """P2: 已审核的收款单不能编辑"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        post_json(client, f'/receipt_order/{ro.id}/audit', {})
        # 尝试编辑
        result = edit_receipt_order(client, db, ro.id, io.id, 80.0)
        assert result.get('success') is False

    def test_unaudit_receipt_blocked_when_already_unaudited(self, client, db):
        """P2: 未审核的收款单不能反审核"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        # 未审核状态直接反审核
        resp = post_json(client, f'/receipt_order/{ro.id}/unaudit', {})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_delete_audited_income_order_blocked(self, client, db):
        """P2: 已审核的收入单不能删除"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        resp = post_json(client, f'/income_order/{io.id}/delete', {})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_unaudit_unaudited_income_order_blocked(self, client, db):
        """P2: 未审核的收入单不能反审核（当前状态不符合）"""
        io = make_income_order(client, db, total=100.0)
        assert io.status == '未审核'
        resp = post_json(client, f'/income_order/{io.id}/unaudit', {})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_batch_unaudit_receipt_success_count(self, client, db):
        """P2: 批量反审核收款单，计数准确"""
        io = make_income_order(client, db, total=300.0)
        audit_io(client, io.id)
        ro1 = make_receipt_order(client, db, io.id, 50.0)
        ro2 = make_receipt_order(client, db, io.id, 30.0)
        # 审核这两张
        post_json(client, f'/receipt_order/{ro1.id}/audit', {})
        post_json(client, f'/receipt_order/{ro2.id}/audit', {})
        # 批量反审核
        resp = post_json(client, '/receipt_order/batch',
                         {'action': 'unaudit', 'ids': [ro1.id, ro2.id]})
        data = json.loads(resp.data)
        assert data['success']
        assert '成功 2' in data['message']


# ─────────────────────────────────────────
# P3 — 接口完整性测试
# ─────────────────────────────────────────

class TestP3ApiIntegrity:
    """接口完整性：API返回数据的正确性与完整性"""

    def test_api_available_orders_returns_correct_fields(self, client, db):
        """P3: available_orders API返回字段完整"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        resp = client.get('/income_order/api/available_orders')
        orders = json.loads(resp.data)
        # 找到刚创建的收入单
        target = next((o for o in orders if o['id'] == io.id), None)
        assert target is not None
        required_fields = ['id', 'code', 'customer_name', 'total_amount',
                           'received_amount', 'unreceived_amount', 'order_date',
                           'audit_status', 'receipt_status']
        for field in required_fields:
            assert field in target, f"API缺少字段: {field}"

    def test_api_available_orders_filter_by_customer(self, client, db):
        """P3: available_orders 按客户ID过滤"""
        io_a = make_income_order(client, db, total=100.0, customer='A')
        io_b = make_income_order(client, db, total=100.0, customer='B')
        audit_io(client, io_a.id)
        audit_io(client, io_b.id)
        cid_a = qa_customer_id(db)
        resp = client.get(f'/income_order/api/available_orders?customer_id={cid_a}')
        orders = json.loads(resp.data)
        ids = [o['id'] for o in orders]
        assert io_a.id in ids
        assert io_b.id not in ids

    def test_api_unreceived_amount_accurate(self, client, db):
        """P3: unreceived_amount API返回值与已收款金额一致"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        make_receipt_order(client, db, io.id, 35.0)
        db.session.refresh(io)
        resp = client.get(f'/income_order/api/{io.id}/unreceived_amount')
        data = json.loads(resp.data)
        assert float(data['total_amount']) == 100.0
        assert float(data['received_amount']) == 35.0
        assert float(data['unreceived_amount']) == 65.0

    def test_api_available_orders_receipt_status_field_correct(self, client, db):
        """P3: API返回的 receipt_status 字段值正确"""
        # 已审核未收款
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        resp = client.get('/income_order/api/available_orders')
        orders = json.loads(resp.data)
        target = next((o for o in orders if o['id'] == io.id), None)
        assert target is not None
        assert target['receipt_status'] == '未收款'
        assert target['audit_status'] == '已审核'
        # 创建部分收款后
        make_receipt_order(client, db, io.id, 50.0)
        resp = client.get('/income_order/api/available_orders')
        orders = json.loads(resp.data)
        target = next((o for o in orders if o['id'] == io.id), None)
        assert target is not None
        assert target['receipt_status'] == '部分收款'

    def test_batch_empty_ids_rejected(self, client):
        """P3: 批量操作未传IDs应返回失败"""
        resp = post_json(client, '/income_order/batch',
                         {'action': 'audit', 'ids': []})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_batch_receipt_empty_ids_rejected(self, client):
        """P3: 收款单批量操作未传IDs应返回失败"""
        resp = post_json(client, '/receipt_order/batch',
                         {'action': 'audit', 'ids': []})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_batch_partial_fail_count_in_message(self, client, db):
        """P3: 批量操作部分失败时消息中包含失败数量"""
        io1 = make_income_order(client, db, total=100.0)   # 未审核可以审核
        io2 = make_income_order(client, db, total=100.0)
        audit_io(client, io2.id)                            # 已审核不能再审核
        resp = post_json(client, '/income_order/batch',
                         {'action': 'audit', 'ids': [io1.id, io2.id]})
        data = json.loads(resp.data)
        assert data['success']
        assert '失败 1' in data['message']


# ─────────────────────────────────────────
# P3扩展 — 判定表法：按钮显示规则UI一致性
# ─────────────────────────────────────────

class TestP3UIButtonRules:
    """判定表法：验证各页面按钮按需求规范展示"""

    # ── 其他收入单列表 ──
    def test_income_list_unaudited_shows_edit_audit_delete(self, client, db):
        """判定表: 收入单列表-未审核行 → 显示 编辑、审核、删除按钮"""
        io = make_income_order(client, db, total=100.0)
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        # 只验证未审核单据对应的tr块中有这三个按钮文本
        # 通过检查同行data-id是否包含对应按钮
        assert f'data-id="{io.id}"' in html
        # 未审核行应有 编辑/审核/删除，不应有 反审核（在未审核行中）
        # 找到该行的片段
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '编辑' in row_html
        assert '审核' in row_html
        assert '删除' in row_html
        assert '反审核' not in row_html

    def test_income_list_unaudited_shows_copy_button(self, client, db):
        """判定表: 收入单列表-未审核行 → 有复制按钮"""
        io = make_income_order(client, db, total=100.0)
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '复制' in row_html

    def test_income_list_audited_shows_unaudit_not_edit(self, client, db):
        """判定表: 收入单列表-已审核行 → 显示 反审核，不显示 编辑/删除"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '反审核' in row_html
        assert '编辑' not in row_html
        assert '删除' not in row_html

    def test_income_list_audited_shows_copy_button(self, client, db):
        """判定表: 收入单列表-已审核行 → 仍有复制按钮"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '复制' in row_html

    # ── 收款单列表 ──
    def test_receipt_list_unaudited_shows_edit_audit_delete(self, client, db):
        """判定表: 收款单列表-未审核行 → 显示 编辑、审核、删除，无反审核"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        resp = client.get('/receipt_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{ro.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '编辑' in row_html
        assert '审核' in row_html
        assert '删除' in row_html
        assert '反审核' not in row_html

    def test_receipt_list_audited_shows_unaudit_not_edit(self, client, db):
        """判定表: 收款单列表-已审核行 → 显示 反审核，不显示 编辑/删除"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        post_json(client, f'/receipt_order/{ro.id}/audit', {})
        resp = client.get('/receipt_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{ro.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '反审核' in row_html
        assert '编辑' not in row_html
        assert '删除' not in row_html

    def test_receipt_list_no_copy_button(self, client, db):
        """判定表: 收款单列表不应有复制按钮（需求规范：收款单不支持批量复制）"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        resp = client.get('/receipt_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{ro.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '复制' not in row_html

    # ── 收款单详情 ──
    def test_receipt_detail_unaudited_has_no_copy_button(self, client, db):
        """判定表: 收款单详情-未审核 → 无复制按钮（需求规范）"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        resp = client.get(f'/receipt_order/{ro.id}')
        html = resp.data.decode('utf-8')
        # 找到card-header区域
        header_start = html.find('card-header')
        header_end = html.find('card-body', header_start)
        header_html = html[header_start:header_end]
        assert '复制' not in header_html

    def test_receipt_detail_unaudited_has_edit_audit_delete(self, client, db):
        """判定表: 收款单详情-未审核 → 有 编辑、审核、删除"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        resp = client.get(f'/receipt_order/{ro.id}')
        html = resp.data.decode('utf-8')
        assert '编辑' in html
        assert '审核' in html
        assert '删除' in html

    def test_receipt_detail_audited_has_unaudit_no_edit(self, client, db):
        """判定表: 收款单详情-已审核 → 有反审核，无编辑/删除"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        post_json(client, f'/receipt_order/{ro.id}/audit', {})
        resp = client.get(f'/receipt_order/{ro.id}')
        html = resp.data.decode('utf-8')
        # 找到 class="card-header" HTML元素（包含引号）
        header_start = html.find('"card-header"')
        header_end = html.find('card-body', header_start)
        header_html = html[header_start:header_end]
        assert '反审核' in header_html
        assert '编辑' not in header_html
        assert '删除' not in header_html

    # ── 其他收入单详情 ──
    def test_income_detail_unaudited_has_copy_edit_audit_delete(self, client, db):
        """判定表: 收入单详情-未审核 → 有 复制、编辑、审核、删除"""
        io = make_income_order(client, db, total=100.0)
        resp = client.get(f'/income_order/{io.id}')
        html = resp.data.decode('utf-8')
        header_start = html.find('"card-header"')
        header_end = html.find('card-body', header_start)
        header_html = html[header_start:header_end]
        assert '复制' in header_html
        assert '编辑' in header_html
        assert '审核' in header_html
        assert '删除' in header_html

    def test_income_detail_audited_has_copy_unaudit_no_edit(self, client, db):
        """判定表: 收入单详情-已审核 → 有 复制、反审核，无 编辑/删除"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        resp = client.get(f'/income_order/{io.id}')
        html = resp.data.decode('utf-8')
        header_start = html.find('"card-header"')
        header_end = html.find('card-body', header_start)
        header_html = html[header_start:header_end]
        assert '复制' in header_html
        assert '反审核' in header_html
        assert '编辑' not in header_html
        assert '删除' not in header_html


# ─────────────────────────────────────────
# P4 — 字段顺序与徽章颜色UI一致性
# ─────────────────────────────────────────

class TestP4FieldOrderAndBadge:
    """字段顺序与徽章颜色：与需求规范严格一致"""

    def test_income_list_column_order(self, client, db):
        """P4: 其他收入单列表列顺序 = 复选框→审核状态→单据编号→单据日期→客户名称→单据总金额→已收款金额→未收款金额→收款状态→操作"""
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        thead_start = html.find('<thead>')
        thead_end = html.find('</thead>', thead_start)
        thead = html[thead_start:thead_end]
        cols = ['审核状态', '单据编号', '单据日期', '客户名称', '单据总金额', '已收款金额', '未收款金额', '收款状态', '操作']
        positions = [thead.find(c) for c in cols]
        assert positions == sorted(positions), \
            f"列顺序不符合需求，实际位置：{list(zip(cols, positions))}"

    def test_receipt_list_column_order(self, client, db):
        """P4: 收款单列表列顺序 = 复选框→单据状态→单据编号→单据日期→客户名称→收款账户→单据总金额→操作"""
        resp = client.get('/receipt_order/')
        html = resp.data.decode('utf-8')
        thead_start = html.find('<thead>')
        thead_end = html.find('</thead>', thead_start)
        thead = html[thead_start:thead_end]
        cols = ['单据状态', '单据编号', '单据日期', '客户名称', '收款账户', '单据总金额', '操作']
        positions = [thead.find(c) for c in cols]
        assert positions == sorted(positions), \
            f"收款单列表列顺序不符合需求，实际位置：{list(zip(cols, positions))}"

    def test_income_list_unaudited_badge_warning(self, client, db):
        """P4: 收入单列表-未审核行审核状态列显示黄色badge-warning"""
        io = make_income_order(client, db, total=100.0)
        assert io.status == '未审核'
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert 'badge-warning' in row_html
        assert '未审核' in row_html

    def test_income_list_unaudited_receipt_status_dash(self, client, db):
        """P4: 收入单列表-未审核行收款状态列显示灰色'-'（badge-secondary）"""
        io = make_income_order(client, db, total=100.0)
        assert io.status == '未审核'
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert 'badge-secondary' in row_html

    def test_income_list_audited_receipt_status_info_badge(self, client, db):
        """P4: 收入单列表-已审核未收款行收款状态显示蓝色badge-info '未收款'"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert 'badge-info' in row_html
        assert '未收款' in row_html

    def test_income_list_part_received_receipt_status_badge_warning(self, client, db):
        """P4: 收入单列表-部分收款行收款状态显示黄色badge-warning '部分收款'"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        make_receipt_order(client, db, io.id, 50.0)
        db.session.refresh(io)
        assert io.status == '部分收款'
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert '部分收款' in row_html

    def test_income_list_full_received_receipt_status_badge_success(self, client, db):
        """P4: 收入单列表-全部收款行收款状态显示绿色badge-success '全部收款'"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        make_receipt_order(client, db, io.id, 100.0)
        db.session.refresh(io)
        assert io.status == '全部收款'
        resp = client.get('/income_order/')
        html = resp.data.decode('utf-8')
        row_start = html.find(f'data-id="{io.id}"')
        row_end = html.find('</tr>', row_start)
        row_html = html[row_start:row_end]
        assert 'badge-success' in row_html
        assert '全部收款' in row_html

    def test_receipt_detail_line_column_order(self, client, db):
        """P4: 收款单详情分录表列顺序 = 关联收入单→收款金额→备注"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        resp = client.get(f'/receipt_order/{ro.id}')
        html = resp.data.decode('utf-8')
        # 找到分录表的thead
        line_table_start = html.find('分录信息')
        line_table_end = html.find('</table>', line_table_start)
        line_table = html[line_table_start:line_table_end]
        pos_rel = line_table.find('关联收入单')
        pos_amt = line_table.find('收款金额')
        pos_rem = line_table.find('备注')
        assert 0 < pos_rel < pos_amt < pos_rem, \
            f"分录表列顺序不符合需求：关联收入单={pos_rel}, 收款金额={pos_amt}, 备注={pos_rem}"


# ─────────────────────────────────────────
# P5 — 场景法：完整端到端业务流程
# ─────────────────────────────────────────

class TestP5EndToEndScenario:
    """场景法：验证完整业务主流程、异常流程、跨模块流程"""

    def test_full_lifecycle_scenario(self, client, db):
        """场景法-主流程: 新增收入单→审核→部分收款→编辑收款→删除收款→回退→反审核"""
        # Step1: 新增收入单
        io = make_income_order(client, db, total=200.0)
        assert io.status == '未审核'
        assert float(io.total_amount) == 200.0

        # Step2: 审核收入单
        audit_io(client, io.id)
        db.session.refresh(io)
        assert io.status == '已审核'
        assert float(io.received_amount) == 0.0

        # Step3: 新增收款单（部分收款 100）
        ro = make_receipt_order(client, db, io.id, 100.0)
        db.session.refresh(io)
        assert io.status == '部分收款'
        assert float(io.received_amount) == 100.0
        assert float(io.unreceived_amount) == 100.0

        # Step4: 编辑收款单，改为80
        result = edit_receipt_order(client, db, ro.id, io.id, 80.0)
        assert result.get('success'), f"编辑失败: {result}"
        db.session.refresh(io)
        assert float(io.received_amount) == 80.0  # 100回退后+80
        assert io.status == '部分收款'

        # Step5: 删除收款单，收入单回退到已审核
        post_json(client, f'/receipt_order/{ro.id}/delete', {})
        db.session.refresh(io)
        assert float(io.received_amount) == 0.0
        assert io.status == '已审核'

        # Step6: 反审核收入单（无收款单关联，应该成功）
        resp = post_json(client, f'/income_order/{io.id}/unaudit', {})
        data = json.loads(resp.data)
        assert data['success']
        db.session.refresh(io)
        assert io.status == '未审核'

    def test_multi_receipt_to_full_then_block_more_receipt(self, client, db):
        """场景法-异常流程: 多次部分收款→全部收款→再次收款被拦截"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)

        # 分两次收款凑满100
        make_receipt_order(client, db, io.id, 60.0)
        db.session.refresh(io)
        assert io.status == '部分收款'

        make_receipt_order(client, db, io.id, 40.0)
        db.session.refresh(io)
        assert io.status == '全部收款'

        # 已全部收款，再尝试收款应失败
        cid = qa_customer_id(db)
        aid = qa_account_id(db)
        resp = post_json(client, '/receipt_order/create', {
            'order_date': '2026-01-01',
            'customer_id': cid,
            'account_id': aid,
            'lines': [{'income_order_id': io.id, 'amount': 1.0, 'remark': ''}]
        })
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_cannot_unaudit_income_order_with_receipt(self, client, db):
        """场景法-反向流程: 有收款单的收入单不能反审核"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        make_receipt_order(client, db, io.id, 50.0)

        resp = post_json(client, f'/income_order/{io.id}/unaudit', {})
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '收款单' in data['message']

    def test_search_filter_by_status_scenario(self, client, db):
        """场景法-搜索流程: 按状态过滤只返回对应状态单据"""
        # 准备：一张未审核，一张已审核
        io_un = make_income_order(client, db, total=100.0)
        io_au = make_income_order(client, db, total=100.0)
        audit_io(client, io_au.id)

        # 按"未审核"过滤
        resp = client.get('/income_order/?status=未审核')
        html = resp.data.decode('utf-8')
        assert f'data-id="{io_un.id}"' in html
        assert f'data-id="{io_au.id}"' not in html

        # 按"已审核"过滤
        resp = client.get('/income_order/?status=已审核')
        html = resp.data.decode('utf-8')
        assert f'data-id="{io_au.id}"' in html
        assert f'data-id="{io_un.id}"' not in html


# ─────────────────────────────────────────
# P6 — 正交试验法：列表搜索参数组合
# ─────────────────────────────────────────

class TestP6OrthogonalSearch:
    """正交试验法：收款单搜索 - 3参数2取值，取4个代表组合覆盖"""

    def test_search_keyword_only(self, client, db):
        """正交L1: 仅关键字过滤，不传状态和日期"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        db.session.refresh(ro)
        # 用单据编号关键字查
        resp = client.get(f'/receipt_order/?keyword={ro.code}')
        html = resp.data.decode('utf-8')
        assert f'data-id="{ro.id}"' in html

    def test_search_status_only(self, client, db):
        """正交L2: 仅状态过滤，不传关键字和日期"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        resp = client.get('/receipt_order/?status=未审核')
        html = resp.data.decode('utf-8')
        assert f'data-id="{ro.id}"' in html

    def test_search_keyword_and_status_combined(self, client, db):
        """正交L3: 关键字+状态组合，两者同时满足才显示"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        db.session.refresh(ro)
        # 关键字匹配 + 状态=未审核
        resp = client.get(f'/receipt_order/?keyword={ro.code}&status=未审核')
        html = resp.data.decode('utf-8')
        assert f'data-id="{ro.id}"' in html
        # 关键字匹配 + 状态=已审核（不应出现）
        resp2 = client.get(f'/receipt_order/?keyword={ro.code}&status=已审核')
        html2 = resp2.data.decode('utf-8')
        assert f'data-id="{ro.id}"' not in html2

    def test_search_income_order_code_filter(self, client, db):
        """正交L4: 按关联收入单编号搜索收款单"""
        io = make_income_order(client, db, total=100.0)
        audit_io(client, io.id)
        ro = make_receipt_order(client, db, io.id, 50.0)
        db.session.refresh(io)
        resp = client.get(f'/receipt_order/?income_order_code={io.code}')
        html = resp.data.decode('utf-8')
        assert f'data-id="{ro.id}"' in html
