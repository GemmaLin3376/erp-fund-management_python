"""
ERP资金管理系统单元测试
覆盖：基础资料、其他收入单、收款单、状态反写、业务规则
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    """创建测试用Flask应用（session级别，整个测试共用一个app实例）"""
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
        _seed_data(_db)
        yield _app
        _db.session.remove()
        _db.drop_all()


def _seed_data(db):
    """初始化测试基础数据（保证code不与init_data冲突，使用TEST前缀）"""
    from app.models import Customer, Account, IncomeCategory

    if not Customer.query.filter_by(code='T_KH001').first():
        db.session.add(Customer(code='T_KH001', name='测试客户A'))
    if not Customer.query.filter_by(code='T_KH002').first():
        db.session.add(Customer(code='T_KH002', name='测试客户B'))
    if not IncomeCategory.query.filter_by(code='T_SR001').first():
        db.session.add(IncomeCategory(code='T_SR001', name='测试服务收入'))
    if not Account.query.filter_by(code='T_ZH001').first():
        db.session.add(Account(code='T_ZH001', name='测试工商银行'))
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


def get_customer_id(db, name='测试客户A'):
    from app.models import Customer
    return Customer.query.filter_by(name=name).first().id


def get_category_id(db):
    from app.models import IncomeCategory
    return IncomeCategory.query.filter_by(code='T_SR001').first().id


def get_account_id(db):
    from app.models import Account
    return Account.query.filter_by(code='T_ZH001').first().id


def create_income_order(client, db, total=100.0):
    """创建并返回一张其他收入单（未审核）"""
    cid = get_customer_id(db)
    cat = get_category_id(db)
    data = {
        'order_date': '2026-01-01',
        'customer_id': cid,
        'lines': [{'category_id': cat, 'amount': total, 'remark': ''}]
    }
    resp = post_json(client, '/income_order/create', data)
    assert resp.status_code == 200, f"创建收入单失败: {resp.data}"
    result = json.loads(resp.data)
    assert result.get('success'), f"创建收入单失败: {result}"
    from app.models.income_order import IncomeOrder
    return IncomeOrder.query.order_by(IncomeOrder.id.desc()).first()


def audit_income_order(client, order_id):
    resp = post_json(client, f'/income_order/{order_id}/audit', {})
    assert resp.status_code == 200
    return json.loads(resp.data)


def create_receipt_order(client, db, income_order_id, amount):
    """创建并返回一张收款单（未审核）"""
    cid = get_customer_id(db)
    aid = get_account_id(db)
    data = {
        'order_date': '2026-01-01',
        'customer_id': cid,
        'account_id': aid,
        'lines': [{'income_order_id': income_order_id, 'amount': amount, 'remark': ''}]
    }
    resp = post_json(client, '/receipt_order/create', data)
    assert resp.status_code == 200, f"创建收款单失败: {resp.data}"
    result = json.loads(resp.data)
    assert result.get('success'), f"创建收款单失败: {result}"
    from app.models.receipt_order import ReceiptOrder
    return ReceiptOrder.query.order_by(ReceiptOrder.id.desc()).first()


# ─────────────────────────────────────────
# T1. 基础资料 - 客户
# ─────────────────────────────────────────

class TestCustomer:

    def test_create_customer_success(self, client):
        """新建客户成功（表单提交）"""
        resp = client.post('/customer/create', data={'name': '测试新客户X'})
        data = json.loads(resp.data)
        assert data['success'] is True

    def test_create_customer_empty_name_fails(self, client):
        """客户名称为空时新建失败"""
        resp = client.post('/customer/create', data={'name': ''})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_delete_customer_unreferenced_success(self, client, db):
        """无引用的客户可以删除"""
        from app.models import Customer
        c = Customer(code='T_KH_DEL', name='待删除测试客户')
        db.session.add(c)
        db.session.commit()
        cid = c.id
        resp = post_json(client, f'/customer/{cid}/delete', {})
        data = json.loads(resp.data)
        assert data['success'] is True

    def test_delete_customer_blocked_when_referenced(self, client, db):
        """客户被收入单引用后不能删除"""
        io = create_income_order(client, db)
        resp = post_json(client, f'/customer/{io.customer_id}/delete', {})
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '引用' in data['message']


# ─────────────────────────────────────────
# T2. 其他收入单 - 基本操作
# ─────────────────────────────────────────

class TestIncomeOrder:

    def test_create_income_order_success(self, client, db):
        """创建收入单成功，初始状态为未审核"""
        io = create_income_order(client, db, total=200.0)
        assert io is not None
        assert float(io.total_amount) == 200.0
        assert io.status == '未审核'

    def test_audit_income_order_changes_status(self, client, db):
        """审核收入单后状态变为已审核"""
        io = create_income_order(client, db)
        result = audit_income_order(client, io.id)
        assert result['success'] is True
        db.session.refresh(io)
        assert io.status == '已审核'

    def test_audit_already_audited_fails(self, client, db):
        """重复审核应返回失败"""
        io = create_income_order(client, db)
        audit_income_order(client, io.id)
        resp = post_json(client, f'/income_order/{io.id}/audit', {})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_unaudit_income_order_success(self, client, db):
        """反审核成功后状态变回未审核"""
        io = create_income_order(client, db)
        audit_income_order(client, io.id)
        resp = post_json(client, f'/income_order/{io.id}/unaudit', {})
        data = json.loads(resp.data)
        assert data['success'] is True
        db.session.refresh(io)
        assert io.status == '未审核'

    def test_unaudit_blocked_when_has_receipt(self, client, db):
        """已关联收款单的收入单不能反审核"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        create_receipt_order(client, db, io.id, 50.0)
        resp = post_json(client, f'/income_order/{io.id}/unaudit', {})
        data = json.loads(resp.data)
        assert data['success'] is False
        assert '收款单' in data['message']

    def test_delete_unaudited_success(self, client, db):
        """未审核的收入单可以删除"""
        io = create_income_order(client, db)
        resp = post_json(client, f'/income_order/{io.id}/delete', {})
        data = json.loads(resp.data)
        assert data['success'] is True

    def test_delete_audited_fails(self, client, db):
        """已审核的收入单不能删除"""
        io = create_income_order(client, db)
        audit_income_order(client, io.id)
        resp = post_json(client, f'/income_order/{io.id}/delete', {})
        data = json.loads(resp.data)
        assert data['success'] is False

    def test_copy_income_order(self, client, db):
        """复制收入单，新单数量+1"""
        from app.models.income_order import IncomeOrder
        io = create_income_order(client, db, total=150.0)
        count_before = IncomeOrder.query.count()
        resp = post_json(client, f'/income_order/{io.id}/copy', {})
        data = json.loads(resp.data)
        assert data['success'] is True
        assert IncomeOrder.query.count() == count_before + 1

    def test_unreceived_amount_property(self, client, db):
        """新建收入单的未收款金额等于总金额"""
        io = create_income_order(client, db, total=100.0)
        assert float(io.unreceived_amount) == 100.0


# ─────────────────────────────────────────
# T3. 收款单 - 基本操作
# ─────────────────────────────────────────

class TestReceiptOrder:

    def test_create_receipt_order_success(self, client, db):
        """创建收款单成功，初始状态未审核"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        assert ro is not None
        assert float(ro.total_amount) == 60.0
        assert ro.status == '未审核'

    def test_audit_receipt_order_success(self, client, db):
        """审核收款单成功，状态变为已审核"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        resp = post_json(client, f'/receipt_order/{ro.id}/audit', {})
        data = json.loads(resp.data)
        assert data['success'] is True
        db.session.refresh(ro)
        assert ro.status == '已审核'

    def test_unaudit_receipt_order_success(self, client, db):
        """反审核收款单成功，状态变回未审核"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        post_json(client, f'/receipt_order/{ro.id}/audit', {})
        resp = post_json(client, f'/receipt_order/{ro.id}/unaudit', {})
        data = json.loads(resp.data)
        assert data['success'] is True
        db.session.refresh(ro)
        assert ro.status == '未审核'

    def test_delete_unaudited_receipt_success(self, client, db):
        """未审核收款单可以删除"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        resp = post_json(client, f'/receipt_order/{ro.id}/delete', {})
        data = json.loads(resp.data)
        assert data['success'] is True

    def test_delete_audited_receipt_fails(self, client, db):
        """已审核收款单不能删除"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        post_json(client, f'/receipt_order/{ro.id}/audit', {})
        resp = post_json(client, f'/receipt_order/{ro.id}/delete', {})
        data = json.loads(resp.data)
        assert data['success'] is False


# ─────────────────────────────────────────
# T4. 核心业务规则 - 状态反写
# ─────────────────────────────────────────

class TestReceiptWriteback:

    def test_save_receipt_updates_income_partial(self, client, db):
        """收款单保存后其他收入单变为部分收款"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        create_receipt_order(client, db, io.id, 60.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 60.0
        assert io.status == '部分收款'

    def test_save_receipt_updates_income_full(self, client, db):
        """收款单保存后其他收入单变为全部收款"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        create_receipt_order(client, db, io.id, 100.0)
        db.session.refresh(io)
        assert float(io.received_amount) == 100.0
        assert io.status == '全部收款'

    def test_delete_receipt_rollback_income_status(self, client, db):
        """删除收款单后其他收入单已收款金额回退为0，状态变为已审核"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        post_json(client, f'/receipt_order/{ro.id}/delete', {})
        db.session.refresh(io)
        assert float(io.received_amount) == 0.0
        assert io.status == '已审核'

    def test_receipt_amount_zero_means_unreceipted(self, client, db):
        """已收款金额为0时状态为已审核（未收款）"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        db.session.refresh(io)
        assert float(io.received_amount) == 0.0
        assert io.status == '已审核'

    def test_audit_receipt_does_not_change_income_status(self, client, db):
        """收款单审核不额外更改收入单状态（保存时已更新）"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        db.session.refresh(io)
        status_before_audit = io.status
        post_json(client, f'/receipt_order/{ro.id}/audit', {})
        db.session.refresh(io)
        assert io.status == status_before_audit

    def test_unaudit_receipt_does_not_rollback_income(self, client, db):
        """收款单反审核不回退收入单状态"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        ro = create_receipt_order(client, db, io.id, 60.0)
        post_json(client, f'/receipt_order/{ro.id}/audit', {})
        db.session.refresh(io)
        status_after_audit = io.status
        post_json(client, f'/receipt_order/{ro.id}/unaudit', {})
        db.session.refresh(io)
        assert io.status == status_after_audit


# ─────────────────────────────────────────
# T5. 选择源单API - 全部收款过滤
# ─────────────────────────────────────────

class TestAvailableOrders:

    def test_fully_received_order_not_in_available(self, client, db):
        """已全部收款的收入单不出现在可选源单列表"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        create_receipt_order(client, db, io.id, 100.0)
        db.session.refresh(io)
        assert io.status == '全部收款'
        resp = client.get('/income_order/api/available_orders')
        orders = json.loads(resp.data)
        ids = [o['id'] for o in orders]
        assert io.id not in ids

    def test_partial_received_order_in_available(self, client, db):
        """部分收款的收入单仍出现在可选源单列表"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        create_receipt_order(client, db, io.id, 60.0)
        db.session.refresh(io)
        assert io.status == '部分收款'
        resp = client.get('/income_order/api/available_orders')
        orders = json.loads(resp.data)
        ids = [o['id'] for o in orders]
        assert io.id in ids

    def test_unaudited_order_not_in_available(self, client, db):
        """未审核的收入单不出现在可选源单列表"""
        io = create_income_order(client, db, total=100.0)
        assert io.status == '未审核'
        resp = client.get('/income_order/api/available_orders')
        orders = json.loads(resp.data)
        ids = [o['id'] for o in orders]
        assert io.id not in ids


# ─────────────────────────────────────────
# T6. 批量操作
# ─────────────────────────────────────────

class TestBatchOperation:

    def test_batch_audit_income_orders(self, client, db):
        """批量审核多张收入单"""
        from app.models.income_order import IncomeOrder
        io1 = create_income_order(client, db, total=100.0)
        io2 = create_income_order(client, db, total=200.0)
        resp = post_json(client, '/income_order/batch',
                         {'action': 'audit', 'ids': [io1.id, io2.id]})
        data = json.loads(resp.data)
        assert data['success'] is True
        db.session.refresh(io1)
        db.session.refresh(io2)
        assert io1.status == '已审核'
        assert io2.status == '已审核'

    def test_batch_delete_unaudited_income_orders(self, client, db):
        """批量删除未审核收入单"""
        from app.models.income_order import IncomeOrder
        io1 = create_income_order(client, db, total=100.0)
        io2 = create_income_order(client, db, total=200.0)
        ids = [io1.id, io2.id]
        resp = post_json(client, '/income_order/batch',
                         {'action': 'delete', 'ids': ids})
        data = json.loads(resp.data)
        assert data['success'] is True
        for oid in ids:
            assert IncomeOrder.query.get(oid) is None

    def test_batch_unaudit_blocked_with_receipt(self, client, db):
        """批量反审核时已关联收款单的单据应失败"""
        io = create_income_order(client, db, total=100.0)
        audit_income_order(client, io.id)
        create_receipt_order(client, db, io.id, 50.0)
        resp = post_json(client, '/income_order/batch',
                         {'action': 'unaudit', 'ids': [io.id]})
        data = json.loads(resp.data)
        # 批量操作返回的消息应包含失败相关信息
        assert '失败' in data['message']
        db.session.refresh(io)
        assert io.status != '未审核'

    def test_batch_audit_receipt_orders(self, client, db):
        """批量审核多张收款单"""
        from app.models.receipt_order import ReceiptOrder
        io1 = create_income_order(client, db, total=200.0)
        audit_income_order(client, io1.id)
        ro1 = create_receipt_order(client, db, io1.id, 50.0)
        io2 = create_income_order(client, db, total=100.0)
        audit_income_order(client, io2.id)
        ro2 = create_receipt_order(client, db, io2.id, 30.0)
        resp = post_json(client, '/receipt_order/batch',
                         {'action': 'audit', 'ids': [ro1.id, ro2.id]})
        data = json.loads(resp.data)
        assert data['success'] is True
        db.session.refresh(ro1)
        db.session.refresh(ro2)
        assert ro1.status == '已审核'
        assert ro2.status == '已审核'
