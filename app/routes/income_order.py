from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from decimal import Decimal
from app import db
from app.models import IncomeOrder, IncomeOrderLine, Customer, IncomeCategory
from app.models.receipt_order import ReceiptOrder, ReceiptOrderLine
from app.utils.code_generator import CodeGenerator

bp = Blueprint('income_order', __name__)

@bp.route('/')
def list_orders():
    """其他收入单列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = IncomeOrder.query
    
    if keyword:
        query = query.filter(
            db.or_(
                IncomeOrder.code.like(f'%{keyword}%'),
                IncomeOrder.customer.has(Customer.name.like(f'%{keyword}%'))
            )
        )
    
    if status:
        query = query.filter(IncomeOrder.status == status)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(IncomeOrder.order_date >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(IncomeOrder.order_date <= date_to_obj)
        except ValueError:
            pass
    
    pagination = query.order_by(IncomeOrder.code.desc()).paginate(page=page, per_page=per_page, error_out=False)
    orders = pagination.items
    
    return render_template('income_order/list.html', 
                         orders=orders, 
                         pagination=pagination,
                         keyword=keyword,
                         status=status,
                         date_from=date_from,
                         date_to=date_to,
                         statuses=[
                             IncomeOrder.STATUS_UNAUDITED,
                             IncomeOrder.STATUS_AUDITED,
                             IncomeOrder.STATUS_PART_RECEIVED,
                             IncomeOrder.STATUS_FULL_RECEIVED
                         ])

@bp.route('/create', methods=['GET', 'POST'])
def create_order():
    """新增其他收入单"""
    if request.method == 'POST':
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': '无效的请求数据'})
        
        order_date = data.get('order_date')
        customer_id = data.get('customer_id')
        lines = data.get('lines', [])
        
        if not customer_id:
            return jsonify({'success': False, 'message': '请选择客户'})
        
        if not lines or len(lines) == 0:
            return jsonify({'success': False, 'message': '请至少添加一条分录'})
        
        # 生成编码
        code = CodeGenerator.generate_code(IncomeOrder, 'income_order')
        
        # 解析日期
        try:
            order_date_obj = datetime.strptime(order_date, '%Y-%m-%d').date() if order_date else datetime.now().date()
        except ValueError:
            order_date_obj = datetime.now().date()
        
        # 创建主单
        order = IncomeOrder(
            code=code,
            order_date=order_date_obj,
            customer_id=customer_id,
            status=IncomeOrder.STATUS_UNAUDITED,
            total_amount=0
        )
        db.session.add(order)
        db.session.flush()  # 获取order.id
        
        # 创建分录
        total_amount = Decimal('0')
        for line_data in lines:
            category_id = line_data.get('category_id')
            amount = line_data.get('amount')
            remark = line_data.get('remark', '')
            
            if not category_id or not amount:
                db.session.rollback()
                return jsonify({'success': False, 'message': '分录信息不完整'})
            
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    db.session.rollback()
                    return jsonify({'success': False, 'message': '金额必须大于0'})
            except:
                db.session.rollback()
                return jsonify({'success': False, 'message': '金额格式不正确'})
            
            line = IncomeOrderLine(
                order_id=order.id,
                category_id=category_id,
                amount=amount_decimal,
                remark=remark
            )
            db.session.add(line)
            total_amount += amount_decimal
        
        order.total_amount = total_amount
        db.session.commit()
        
        return jsonify({'success': True, 'message': '创建成功', 'redirect': url_for('income_order.list_orders')})
    
    # 生成新编码供显示
    new_code = CodeGenerator.generate_code(IncomeOrder, 'income_order')
    customers = Customer.query.order_by(Customer.code).all()
    categories = IncomeCategory.query.order_by(IncomeCategory.code).all()
    
    return render_template('income_order/form.html', 
                         order=None, 
                         new_code=new_code,
                         customers=customers,
                         categories=categories,
                         today=datetime.now().strftime('%Y-%m-%d'))

@bp.route('/<int:id>')
def view_order(id):
    """查看其他收入单详情"""
    order = IncomeOrder.query.get_or_404(id)
    lines = order.lines.all()
    receipt_details = order.get_receipt_details() if order.status in [IncomeOrder.STATUS_PART_RECEIVED, IncomeOrder.STATUS_FULL_RECEIVED] else []
    
    return render_template('income_order/detail.html', 
                         order=order, 
                         lines=lines,
                         receipt_details=receipt_details)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_order(id):
    """编辑其他收入单"""
    order = IncomeOrder.query.get_or_404(id)
    
    # 只有未审核状态才能编辑
    if order.status != IncomeOrder.STATUS_UNAUDITED:
        return jsonify({'success': False, 'message': '只有未审核单据才能编辑'}), 400
    
    if request.method == 'POST':
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': '无效的请求数据'})
        
        order_date = data.get('order_date')
        customer_id = data.get('customer_id')
        lines = data.get('lines', [])
        
        if not customer_id:
            return jsonify({'success': False, 'message': '请选择客户'})
        
        if not lines or len(lines) == 0:
            return jsonify({'success': False, 'message': '请至少添加一条分录'})
        
        # 更新主单
        try:
            order.order_date = datetime.strptime(order_date, '%Y-%m-%d').date() if order_date else datetime.now().date()
        except ValueError:
            order.order_date = datetime.now().date()
        
        order.customer_id = customer_id
        
        # 删除旧分录
        for line in order.lines.all():
            db.session.delete(line)
        
        # 创建新分录
        total_amount = Decimal('0')
        for line_data in lines:
            category_id = line_data.get('category_id')
            amount = line_data.get('amount')
            remark = line_data.get('remark', '')
            
            if not category_id or not amount:
                db.session.rollback()
                return jsonify({'success': False, 'message': '分录信息不完整'})
            
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal <= 0:
                    db.session.rollback()
                    return jsonify({'success': False, 'message': '金额必须大于0'})
            except:
                db.session.rollback()
                return jsonify({'success': False, 'message': '金额格式不正确'})
            
            line = IncomeOrderLine(
                order_id=order.id,
                category_id=category_id,
                amount=amount_decimal,
                remark=remark
            )
            db.session.add(line)
            total_amount += amount_decimal
        
        order.total_amount = total_amount
        db.session.commit()
        
        return jsonify({'success': True, 'message': '修改成功', 'redirect': url_for('income_order.list_orders')})
    
    customers = Customer.query.order_by(Customer.code).all()
    categories = IncomeCategory.query.order_by(IncomeCategory.code).all()
    lines = order.lines.all()
    
    return render_template('income_order/form.html', 
                         order=order,
                         customers=customers,
                         categories=categories,
                         lines=lines)

@bp.route('/<int:id>/delete', methods=['POST'])
def delete_order(id):
    """删除其他收入单"""
    order = IncomeOrder.query.get_or_404(id)
    
    # 只有未审核状态才能删除
    if order.status != IncomeOrder.STATUS_UNAUDITED:
        return jsonify({'success': False, 'message': '只有未审核单据才能删除'})
    
    # 删除分录
    for line in order.lines.all():
        db.session.delete(line)
    
    # 删除主单
    db.session.delete(order)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '删除成功'})

@bp.route('/<int:id>/audit', methods=['POST'])
def audit_order(id):
    """审核其他收入单"""
    order = IncomeOrder.query.get_or_404(id)
    
    # 只有未审核状态才能审核
    if order.status != IncomeOrder.STATUS_UNAUDITED:
        return jsonify({'success': False, 'message': '只有未审核单据才能审核'})
    
    order.status = IncomeOrder.STATUS_AUDITED
    db.session.commit()
    
    return jsonify({'success': True, 'message': '审核成功'})

@bp.route('/<int:id>/unaudit', methods=['POST'])
def unaudit_order(id):
    """反审核其他收入单"""
    order = IncomeOrder.query.get_or_404(id)
    
    # 已审核、部分收款、全部收款状态均可尝试反审核（有收款单时会被拦截）
    if order.status not in [IncomeOrder.STATUS_AUDITED, IncomeOrder.STATUS_PART_RECEIVED, IncomeOrder.STATUS_FULL_RECEIVED]:
        return jsonify({'success': False, 'message': '当前状态不能反审核'})
    
    # 检查是否有收款单关联（包括未审核和已审核）
    has_any_receipt = db.session.query(ReceiptOrderLine).join(ReceiptOrder).filter(
        ReceiptOrderLine.income_order_id == order.id
    ).first()
    
    if has_any_receipt:
        return jsonify({'success': False, 'message': '该单据已关联收款单，不能反审核'})
    
    order.status = IncomeOrder.STATUS_UNAUDITED
    order.received_amount = 0
    db.session.commit()
    
    return jsonify({'success': True, 'message': '反审核成功'})

@bp.route('/<int:id>/copy', methods=['POST'])
def copy_order(id):
    """复制其他收入单"""
    source_order = IncomeOrder.query.get_or_404(id)
    
    # 生成新编码
    code = CodeGenerator.generate_code(IncomeOrder, 'income_order')
    
    # 创建新单据
    new_order = IncomeOrder(
        code=code,
        order_date=datetime.now().date(),
        customer_id=source_order.customer_id,
        status=IncomeOrder.STATUS_UNAUDITED,
        total_amount=source_order.total_amount
    )
    db.session.add(new_order)
    db.session.flush()
    
    # 复制分录
    for line in source_order.lines.all():
        new_line = IncomeOrderLine(
            order_id=new_order.id,
            category_id=line.category_id,
            amount=line.amount,
            remark=line.remark
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
        order = IncomeOrder.query.get(id)
        if not order:
            fail_count += 1
            continue
        
        try:
            if action == 'copy':
                # 复制逻辑
                code = CodeGenerator.generate_code(IncomeOrder, 'income_order')
                new_order = IncomeOrder(
                    code=code,
                    order_date=datetime.now().date(),
                    customer_id=order.customer_id,
                    status=IncomeOrder.STATUS_UNAUDITED,
                    total_amount=order.total_amount
                )
                db.session.add(new_order)
                db.session.flush()
                
                for line in order.lines.all():
                    new_line = IncomeOrderLine(
                        order_id=new_order.id,
                        category_id=line.category_id,
                        amount=line.amount,
                        remark=line.remark
                    )
                    db.session.add(new_line)
                success_count += 1
                
            elif action == 'audit':
                if order.status == IncomeOrder.STATUS_UNAUDITED:
                    order.status = IncomeOrder.STATUS_AUDITED
                    success_count += 1
                else:
                    fail_count += 1
                    fail_messages.append(f"{order.code}：已审核单据不能再次审核")
                    
            elif action == 'unaudit':
                if order.status in [IncomeOrder.STATUS_AUDITED, IncomeOrder.STATUS_PART_RECEIVED, IncomeOrder.STATUS_FULL_RECEIVED]:
                    # 检查是否有收款单关联（包括未审核和已审核）
                    has_any_receipt = db.session.query(ReceiptOrderLine).join(ReceiptOrder).filter(
                        ReceiptOrderLine.income_order_id == order.id
                    ).first()
                    if has_any_receipt:
                        fail_count += 1
                        fail_messages.append(f"{order.code}：该单据已关联收款单，不能反审核")
                    else:
                        order.status = IncomeOrder.STATUS_UNAUDITED
                        order.received_amount = 0
                        success_count += 1
                else:
                    fail_count += 1
                    fail_messages.append(f"{order.code}：当前状态为未审核，不能反审核")
                    
            elif action == 'delete':
                if order.status == IncomeOrder.STATUS_UNAUDITED:
                    for line in order.lines.all():
                        db.session.delete(line)
                    db.session.delete(order)
                    success_count += 1
                else:
                    fail_count += 1
                    fail_messages.append(f"{order.code}：已审核单据不能删除")
                    
        except Exception as e:
            fail_count += 1
            fail_messages.append(str(e))
    
    db.session.commit()
    
    message = f'操作完成：成功 {success_count} 条'
    if fail_count > 0:
        message += f'，失败 {fail_count} 条'
        if fail_messages:
            message += '\n\n失败详情：\n' + '\n'.join(fail_messages)
    
    return jsonify({'success': True, 'message': message})

@bp.route('/api/available_orders')
def api_available_orders():
    """API：获取可关联的其他收入单（已审核、部分收款状态，且未全部收款）"""
    customer_id = request.args.get('customer_id', type=int)
    
    query = IncomeOrder.query.filter(
        db.or_(
            IncomeOrder.status == IncomeOrder.STATUS_AUDITED,
            IncomeOrder.status == IncomeOrder.STATUS_PART_RECEIVED
        )
    )
    
    if customer_id:
        query = query.filter(IncomeOrder.customer_id == customer_id)
    
    orders = query.order_by(IncomeOrder.code.desc()).all()
    
    result = []
    for order in orders:
        # 过滤已收款的单据（未收款金额为0）
        if order.unreceived_amount <= 0:
            continue
        result.append({
            'id': order.id,
            'code': order.code,
            'customer_id': order.customer_id,
            'customer_name': order.customer.name if order.customer else '',
            'total_amount': float(order.total_amount),
            'received_amount': float(order.received_amount),
            'unreceived_amount': order.unreceived_amount,
            'order_date': order.order_date.strftime('%Y-%m-%d') if order.order_date else None,
            'audit_status': '已审核' if order.status != IncomeOrder.STATUS_UNAUDITED else '未审核',
            'receipt_status': '未收款' if order.status == IncomeOrder.STATUS_AUDITED else ('部分收款' if order.status == IncomeOrder.STATUS_PART_RECEIVED else '全部收款')
        })
    
    return jsonify(result)

@bp.route('/api/<int:id>/unreceived_amount')
def api_unreceived_amount(id):
    """API：获取收入单未收款金额"""
    order = IncomeOrder.query.get_or_404(id)
    return jsonify({
        'id': order.id,
        'code': order.code,
        'unreceived_amount': order.unreceived_amount,
        'total_amount': float(order.total_amount),
        'received_amount': float(order.received_amount)
    })
