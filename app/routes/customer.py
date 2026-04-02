from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app import db
from app.models import Customer
from app.utils.code_generator import CodeGenerator

bp = Blueprint('customer', __name__)

@bp.route('/')
def list_customers():
    """客户列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    keyword = request.args.get('keyword', '')
    
    query = Customer.query
    if keyword:
        query = query.filter(
            db.or_(
                Customer.code.like(f'%{keyword}%'),
                Customer.name.like(f'%{keyword}%')
            )
        )
    
    pagination = query.order_by(Customer.code).paginate(page=page, per_page=per_page, error_out=False)
    customers = pagination.items
    
    return render_template('customer/list.html', 
                         customers=customers, 
                         pagination=pagination,
                         keyword=keyword)

@bp.route('/create', methods=['GET', 'POST'])
def create_customer():
    """新增客户"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': '客户名称不能为空'})
        
        # 生成编码
        code = CodeGenerator.generate_code(Customer, 'customer')
        
        customer = Customer(code=code, name=name)
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '创建成功', 'redirect': url_for('customer.list_customers')})
    
    # 生成新编码供显示
    new_code = CodeGenerator.generate_code(Customer, 'customer')
    return render_template('customer/form.html', customer=None, new_code=new_code)

@bp.route('/<int:id>')
def view_customer(id):
    """查看客户详情"""
    customer = Customer.query.get_or_404(id)
    return render_template('customer/detail.html', customer=customer)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_customer(id):
    """编辑客户"""
    customer = Customer.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': '客户名称不能为空'})
        
        customer.name = name
        db.session.commit()
        
        return jsonify({'success': True, 'message': '修改成功', 'redirect': url_for('customer.list_customers')})
    
    return render_template('customer/form.html', customer=customer)

@bp.route('/<int:id>/delete', methods=['POST'])
def delete_customer(id):
    """删除客户"""
    customer = Customer.query.get_or_404(id)
    
    # 检查是否被其他单据引用
    if customer.income_orders.count() > 0 or customer.receipt_orders.count() > 0:
        return jsonify({'success': False, 'message': '该客户已被单据引用，不能删除'})
    
    db.session.delete(customer)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '删除成功'})

@bp.route('/api/list')
def api_list_customers():
    """API：获取客户列表（用于下拉选择）"""
    customers = Customer.query.order_by(Customer.code).all()
    return jsonify([customer.to_dict() for customer in customers])
