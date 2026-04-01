from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app import db
from app.models import IncomeCategory
from app.utils.code_generator import CodeGenerator

bp = Blueprint('income_category', __name__)

@bp.route('/')
def list_categories():
    """收入类别列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    keyword = request.args.get('keyword', '')
    
    query = IncomeCategory.query
    if keyword:
        query = query.filter(
            db.or_(
                IncomeCategory.code.like(f'%{keyword}%'),
                IncomeCategory.name.like(f'%{keyword}%')
            )
        )
    
    pagination = query.order_by(IncomeCategory.code).paginate(page=page, per_page=per_page, error_out=False)
    categories = pagination.items
    
    return render_template('income_category/list.html', 
                         categories=categories, 
                         pagination=pagination,
                         keyword=keyword)

@bp.route('/create', methods=['GET', 'POST'])
def create_category():
    """新增收入类别"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': '类别名称不能为空'})
        
        # 生成编码
        code = CodeGenerator.generate_code(IncomeCategory, 'income_category')
        
        category = IncomeCategory(code=code, name=name)
        db.session.add(category)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '创建成功', 'redirect': url_for('income_category.list_categories')})
    
    # 生成新编码供显示
    new_code = CodeGenerator.generate_code(IncomeCategory, 'income_category')
    return render_template('income_category/form.html', category=None, new_code=new_code)

@bp.route('/<int:id>')
def view_category(id):
    """查看收入类别详情"""
    category = IncomeCategory.query.get_or_404(id)
    return render_template('income_category/detail.html', category=category)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit_category(id):
    """编辑收入类别"""
    category = IncomeCategory.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'message': '类别名称不能为空'})
        
        category.name = name
        db.session.commit()
        
        return jsonify({'success': True, 'message': '修改成功', 'redirect': url_for('income_category.list_categories')})
    
    return render_template('income_category/form.html', category=category)

@bp.route('/<int:id>/delete', methods=['POST'])
def delete_category(id):
    """删除收入类别"""
    category = IncomeCategory.query.get_or_404(id)
    
    # 检查是否被其他单据引用
    if category.income_order_lines.count() > 0:
        return jsonify({'success': False, 'message': '该类别已被单据引用，不能删除'})
    
    db.session.delete(category)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '删除成功'})

@bp.route('/api/list')
def api_list_categories():
    """API：获取收入类别列表（用于下拉选择）"""
    categories = IncomeCategory.query.order_by(IncomeCategory.code).all()
    return jsonify([category.to_dict() for category in categories])
