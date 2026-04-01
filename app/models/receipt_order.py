from app import db
from datetime import datetime

class ReceiptOrder(db.Model):
    __tablename__ = 'receipt_orders'
    
    # 状态常量
    STATUS_UNAUDITED = '未审核'
    STATUS_AUDITED = '已审核'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    order_date = db.Column(db.Date, nullable=False, default=datetime.now().date)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_UNAUDITED)
    total_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关联
    lines = db.relationship('ReceiptOrderLine', backref='receipt_order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ReceiptOrder {self.code}: {self.status}>'
    
    def audit(self):
        """审核收款单"""
        if self.status != self.STATUS_UNAUDITED:
            return False, '只有未审核单据才能审核'
        
        self.status = self.STATUS_AUDITED
        db.session.commit()
        
        return True, '审核成功'
    
    def delete(self):
        """删除收款单前处理"""
        if self.status == self.STATUS_AUDITED:
            return False, '已审核单据不能删除'
        
        # 保存关联的收入单ID
        income_order_ids = [line.income_order_id for line in self.lines if line.income_order_id]
        
        # 删除分录
        for line in self.lines:
            db.session.delete(line)
        
        # 删除主单
        db.session.delete(self)
        db.session.commit()
        
        # 更新关联收入单状态（删除时回退已收款金额）
        for income_order_id in set(income_order_ids):
            if income_order_id:
                from app.models.income_order import IncomeOrder
                income_order = IncomeOrder.query.get(income_order_id)
                if income_order:
                    income_order.update_received_amount()
        
        return True, '删除成功'
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'order_date': self.order_date.strftime('%Y-%m-%d') if self.order_date else None,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name if self.customer else None,
            'account_id': self.account_id,
            'account_name': self.account.name if self.account else None,
            'status': self.status,
            'total_amount': float(self.total_amount),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


class ReceiptOrderLine(db.Model):
    __tablename__ = 'receipt_order_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    receipt_order_id = db.Column(db.Integer, db.ForeignKey('receipt_orders.id'), nullable=False)
    income_order_id = db.Column(db.Integer, db.ForeignKey('income_orders.id'), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<ReceiptOrderLine {self.id}: {self.amount}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'receipt_order_id': self.receipt_order_id,
            'income_order_id': self.income_order_id,
            'income_order_code': self.income_order.code if self.income_order else '已删除',
            'amount': float(self.amount),
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
