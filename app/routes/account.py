from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app import db
from app.models import Account
from app.utils.code_generator import CodeGenerator

bp = Blueprint('account', __name__)

@bp.route('/')
def list_accounts():
    """收款账户列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    keyword = request.args.get('keyword', '')
    
    query = Account.query
    if keyword:
        query = query.filter(
            db.or_(
                Account.code.like(f'%{keyword}%'),
                Account.name.like(f'%{keyword}%')
            )
        )
    
    pagination = query.order_by(Account.code).paginate(page=page, per_page=per_page, error_out=False)
    accounts = pagination.items
    
    return render_template('account/list.html', 
                         accounts=accounts, 
                         pagination=pagination,
                         keyword=keyword)

@bp.route('/create', methods=['GET', 'POST'])
def create_account():
    """新增收款账户"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': '账户名称不能为空'})
        
        # 生成编码
        code = CodeGenerator.generate_code(Account, 'account')
        
        account = Account(code=code, name=name)
        db.session.add(account)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '创建成功', 'redirect': url_for('account.list_accounts')})
    
    # 生成新编码供显示
    new_code = CodeGenerator.generate_code(Account, 'account')
    return render_template('account/form.html', account=None, new_code=new_code)

@bp.route('/<int:id>')
def view_account(id):
    """查看收款账户详情"""
    account = Account.query.get_or_404(id)
    return render_template('account/detail.html', account=account)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_account(id):
    """编辑收款账户"""
    account = Account.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': '账户名称不能为空'})
        
        account.name = name
        db.session.commit()
        
        return jsonify({'success': True, 'message': '修改成功', 'redirect': url_for('account.list_accounts')})
    
    return render_template('account/form.html', account=account)

@bp.route('/<int:id>/delete', methods=['POST'])
def delete_account(id):
    """删除收款账户"""
    account = Account.query.get_or_404(id)
    
    # 检查是否被其他单据引用
    if account.receipt_orders.count() > 0:
        return jsonify({'success': False, 'message': '该账户已被单据引用，不能删除'})
    
    db.session.delete(account)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '删除成功'})

@bp.route('/api/list')
def api_list_accounts():
    """API：获取收款账户列表（用于下拉选择）"""
    accounts = Account.query.order_by(Account.code).all()
    return jsonify([account.to_dict() for account in accounts])
