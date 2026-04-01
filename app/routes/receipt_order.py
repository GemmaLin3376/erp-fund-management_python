from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from decimal import Decimal
from app import db
from app.models import ReceiptOrder, ReceiptOrderLine, IncomeOrder, Customer, Account
from app.utils.code_generator import CodeGenerator

bp = Blueprint('receipt_order', __name__)

@bp.route('/')
def list_orders():
    """收款单列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    income_order_code = request.args.get('income_order_code', '')
    
    query = ReceiptOrder.query
    
    if keyword:
        query = query.filter(
            db.or_(
                ReceiptOrder.code.like(f'%{keyword}%'),
                ReceiptOrder.customer.has(Customer.name.like(f'%{keyword}%'))
            )
        )
    
    if status:
        query = query.filter(ReceiptOrder.status == status)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(ReceiptOrder.order_date >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(ReceiptOrder.order_date <= date_to_obj)
        except ValueError:
            pass
    
    if income_order_code:
        query = query.join(ReceiptOrderLine).join(IncomeOrder).filter(IncomeOrder.code.like(f'%{income_order_code}%'))
    
    pagination = query.order_by(ReceiptOrder.code.desc()).paginate(page=page, per_page=per_page, error_out=False)
    orders = pagination.items
    
    return render_template('receipt_order/list.html', 
                         orders=orders, 
                         pagination=pagination,
                         keyword=keyword,
                         status=status,
                         date_from=date_from,
                         date_to=date_to,
                         income_order_code=income_order_code,
                         statuses=[
                             ReceiptOrder.STATUS_UNAUDITED,
                             ReceiptOrder.STATUS_AUDITED
                         ])

@bp.route('/create', methods=['GET', 'POST'])
def create_order():
    """新增收款单"""
    if request.method == 'POST':
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': '无效的请求数据'})
        
        order_date = data.get('order_date')
        customer_id = data.get('customer_id')
        account_id = data.get('account_id')
        lines = data.get('lines', [])
        
        if not customer_id:
            return jsonify({'success': False, 'message': '请选择客户'})
        
        if not account_id:
            return jsonify({'success': False, 'message': '请选择收款账户'})
        
        if not lines or len(lines) == 0:
            return jsonify({'success': False, 'message': '请至少添加一条分录'})
        
        # 生成编码
        code = CodeGenerator.generate_code(ReceiptOrder, 'receipt_order')
        
        # 解析日期
        try:
            order_date_obj = datetime.strptime(order_date, '%Y-%m-%d').date() if order_date else datetime.now().date()
        except ValueError:
            order_date_obj = datetime.now().date()
        
        # 创建主单
        order = ReceiptOrder(
            code=code,
            order_date=order_date_obj,
            customer_id=customer_id,
            account_id=account_id,
            status=ReceiptOrder.STATUS_UNAUDITED,
            total_amount=0
        )
        db.session.add(order)
        db.session.flush()  # 获取order.id
        
        # 创建分录
        total_amount = Decimal('0')
        for line_data in lines:
            income_order_id = line_data.get('income_order_id')
            amount = line_data.get('amount')
            remark = line_data.get('remark', '')
            
            if not income_order_id or amount is None:
                db.session.rollback()
                return jsonify({'success': False, 'message': '分录信息不完整'})
            
            # 检查收入单是否存在且可收款
            income_order = IncomeOrder.query.get(income_order_id)
            if not income_order:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'关联的收入单不存在'})
            
            if income_order.status not in [IncomeOrder.STATUS_AUDITED, IncomeOrder.STATUS_PART_RECEIVED]:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'收入单 {income_order.code} 不可收款'})
            
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    db.session.rollback()
                    return jsonify({'success': False, 'message': '金额必须大于0'})
            except:
                db.session.rollback()
                return jsonify({'success': False, 'message': '金额格式不正确'})
            
            line = ReceiptOrderLine(
                receipt_order_id=order.id,
                income_order_id=income_order_id,
                amount=amount_decimal,
                remark=remark
            )
            db.session.add(line)
            total_amount += amount_decimal
        
        order.total_amount = total_amount
        db.session.commit()
        
        # 保存后立即更新其他收入单的已收款金额和状态
        for line_data in lines:
            income_order_id = line_data.get('income_order_id')
            amount = line_data.get('amount')
            if income_order_id and amount is not None:
                income_order = IncomeOrder.query.get(income_order_id)
                if income_order:
                    # 直接累加已收款金额
                    income_order.received_amount = Decimal(str(income_order.received_amount)) + Decimal(str(amount))
                    # 更新状态
                    if float(income_order.received_amount) >= float(income_order.total_amount):
                        income_order.status = IncomeOrder.STATUS_FULL_RECEIVED
                    elif float(income_order.received_amount) > 0:
                        income_order.status = IncomeOrder.STATUS_PART_RECEIVED
                    else:
                        income_order.status = IncomeOrder.STATUS_AUDITED
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '创建成功', 'redirect': url_for('receipt_order.list_orders')})
    
    # 生成新编码供显示
    new_code = CodeGenerator.generate_code(ReceiptOrder, 'receipt_order')
    customers = Customer.query.order_by(Customer.code).all()
    accounts = Account.query.order_by(Account.code).all()
    
    return render_template('receipt_order/form.html', 
                         order=None, 
                         new_code=new_code,
                         customers=customers,
                         accounts=accounts,
                         today=datetime.now().strftime('%Y-%m-%d'))

@bp.route('/<int:id>')
def view_order(id):
    """查看收款单详情"""
    order = ReceiptOrder.query.get_or_404(id)
    lines = order.lines.all()
    
    return render_template('receipt_order/detail.html', 
                         order=order, 
                         lines=lines)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_order(id):
    """编辑收款单"""
    order = ReceiptOrder.query.get_or_404(id)
    
    # 只有未审核状态才能编辑
    if order.status != ReceiptOrder.STATUS_UNAUDITED:
        return jsonify({'success': False, 'message': '只有未审核单据才能编辑'}), 400
    
    if request.method == 'POST':
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': '无效的请求数据'})
        
        order_date = data.get('order_date')
        customer_id = data.get('customer_id')
        account_id = data.get('account_id')
        lines = data.get('lines', [])
        
        if not customer_id:
            return jsonify({'success': False, 'message': '请选择客户'})
        
        if not account_id:
            return jsonify({'success': False, 'message': '请选择收款账户'})
        
        if not lines or len(lines) == 0:
            return jsonify({'success': False, 'message': '请至少添加一条分录'})
        
        # 更新主单
        try:
            order.order_date = datetime.strptime(order_date, '%Y-%m-%d').date() if order_date else datetime.now().date()
        except ValueError:
            order.order_date = datetime.now().date()
        
        order.customer_id = customer_id
        order.account_id = account_id
        
        # 先回退旧分录关联的收入单已收款金额
        for old_line in order.lines.all():
            if old_line.income_order_id and old_line.amount:
                old_income = IncomeOrder.query.get(old_line.income_order_id)
                if old_income:
                    old_income.received_amount = max(
                        Decimal('0'),
                        Decimal(str(old_income.received_amount)) - Decimal(str(old_line.amount))
                    )
                    if float(old_income.received_amount) >= float(old_income.total_amount):
                        old_income.status = IncomeOrder.STATUS_FULL_RECEIVED
                    elif float(old_income.received_amount) > 0:
                        old_income.status = IncomeOrder.STATUS_PART_RECEIVED
                    else:
                        old_income.status = IncomeOrder.STATUS_AUDITED

        # 删除旧分录
        for line in order.lines.all():
            db.session.delete(line)

        # 创建新分录
        total_amount = Decimal('0')
        for line_data in lines:
            income_order_id = line_data.get('income_order_id')
            amount = line_data.get('amount')
            remark = line_data.get('remark', '')
            
            if not income_order_id or amount is None:
                db.session.rollback()
                return jsonify({'success': False, 'message': '分录信息不完整'})
            
            # 检查收入单是否存在且可收款
            income_order = IncomeOrder.query.get(income_order_id)
            if not income_order:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'关联的收入单不存在'})
            
            if income_order.status not in [IncomeOrder.STATUS_AUDITED, IncomeOrder.STATUS_PART_RECEIVED]:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'收入单 {income_order.code} 不可收款'})
            
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    db.session.rollback()
                    return jsonify({'success': False, 'message': '金额必须大于0'})
            except:
                db.session.rollback()
                return jsonify({'success': False, 'message': '金额格式不正确'})
            
            line = ReceiptOrderLine(
                receipt_order_id=order.id,
                income_order_id=income_order_id,
                amount=amount_decimal,
                remark=remark
            )
            db.session.add(line)
            total_amount += amount_decimal
        
        order.total_amount = total_amount
        db.session.commit()
        
        # 保存后立即更新其他收入单的已收款金额和状态
        for line_data in lines:
            income_order_id = line_data.get('income_order_id')
            amount = line_data.get('amount')
            if income_order_id and amount is not None:
                income_order = IncomeOrder.query.get(income_order_id)
                if income_order:
                    # 直接累加已收款金额
                    income_order.received_amount = Decimal(str(income_order.received_amount)) + Decimal(str(amount))
                    # 更新状态
                    if float(income_order.received_amount) >= float(income_order.total_amount):
                        income_order.status = IncomeOrder.STATUS_FULL_RECEIVED
                    elif float(income_order.received_amount) > 0:
                        income_order.status = IncomeOrder.STATUS_PART_RECEIVED
                    else:
                        income_order.status = IncomeOrder.STATUS_AUDITED
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '修改成功', 'redirect': url_for('receipt_order.list_orders')})
    
    customers = Customer.query.order_by(Customer.code).all()
    accounts = Account.query.order_by(Account.code).all()
    lines = order.lines.all()
    
    return render_template('receipt_order/form.html', 
                         order=order,
                         customers=customers,
                         accounts=accounts,
                         lines=lines)

@bp.route('/<int:id>/delete', methods=['POST'])
def delete_order(id):
    """删除收款单"""
    order = ReceiptOrder.query.get_or_404(id)
    
    success, message = order.delete()
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message})

@bp.route('/<int:id>/audit', methods=['POST'])
def audit_order(id):
    """审核收款单"""
    order = ReceiptOrder.query.get_or_404(id)
    
    success, message = order.audit()
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message})

@bp.route('/<int:id>/unaudit', methods=['POST'])
def unaudit_order(id):
    """反审核收款单"""
    order = ReceiptOrder.query.get_or_404(id)
    
    if order.status != ReceiptOrder.STATUS_AUDITED:
        return jsonify({'success': False, 'message': '只有已审核单据才能反审核'})
    
    order.status = ReceiptOrder.STATUS_UNAUDITED
    db.session.commit()
    
    return jsonify({'success': True, 'message': '反审核成功'})

@bp.route('/<int:id>/copy', methods=['POST'])
def copy_order(id):
    """复制收款单"""
    source_order = ReceiptOrder.query.get_or_404(id)
    
    # 生成新编码
    code = CodeGenerator.generate_code(ReceiptOrder, 'receipt_order')
    
    # 创建新单据
    new_order = ReceiptOrder(
        code=code,
        order_date=datetime.now().date(),
        customer_id=source_order.customer_id,
        account_id=source_order.account_id,
        status=ReceiptOrder.STATUS_UNAUDITED,
        total_amount=source_order.total_amount
    )
    db.session.add(new_order)
    db.session.flush()
    
    # 复制分录
    for line in source_order.lines:
        new_line = ReceiptOrderLine(
            receipt_order_id=new_order.id,
            income_order_id=line.income_order_id,
            amount=line.amount
        )
        db.session.add(new_line)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': '复制成功', 'new_code': code})

@bp.route('/batch', methods=['POST'])
def batch_operation():
    """批量操作"""
    data = request.get_json()
    action = data.get('action')
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'success': False, 'message': '未选择记录'})
    
    success_count = 0
    fail_count = 0
    fail_messages = []
    
    for id in ids:
        order = ReceiptOrder.query.get(id)
        if not order:
            fail_count += 1
            continue
        
        try:
            if action == 'audit':
                if order.status == ReceiptOrder.STATUS_UNAUDITED:
                    success, _ = order.audit()
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        fail_messages.append(f"{order.code}：审核失败")
                else:
                    fail_count += 1
                    fail_messages.append(f"{order.code}：已审核单据不能再次审核")
                    
            elif action == 'unaudit':
                if order.status == ReceiptOrder.STATUS_AUDITED:
                    order.status = ReceiptOrder.STATUS_UNAUDITED
                    success_count += 1
                else:
                    fail_count += 1
                    fail_messages.append(f"{order.code}：未审核单据不能反审核")
                    
            elif action == 'delete':
                if order.status == ReceiptOrder.STATUS_UNAUDITED:
                    success, _ = order.delete()
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        fail_messages.append(f"{order.code}：删除失败")
                else:
                    fail_count += 1
                    fail_messages.append(f"{order.code}：已审核单据不能删除")
                    
        except Exception as e:
            fail_count += 1
            fail_messages.append(f"{order.code}：{str(e)}")
            continue
    
    db.session.commit()
    
    message = f'操作完成：成功 {success_count} 条，失败 {fail_count} 条'
    if fail_messages:
        message += '\n\n失败详情：\n' + '\n'.join(fail_messages)
    
    return jsonify({
        'success': True,
        'message': message
    })
