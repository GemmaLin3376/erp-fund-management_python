from app import db
from datetime import datetime

class IncomeOrder(db.Model):
    __tablename__ = 'income_orders'
    
    # 状态常量
    STATUS_UNAUDITED = '未审核'
    STATUS_AUDITED = '已审核'
    STATUS_PART_RECEIVED = '部分收款'
    STATUS_FULL_RECEIVED = '全部收款'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    order_date = db.Column(db.Date, nullable=False, default=datetime.now().date)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_UNAUDITED)
    total_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    received_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关联
    lines = db.relationship('IncomeOrderLine', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    receipt_lines = db.relationship('ReceiptOrderLine', backref='income_order', lazy='dynamic')
    
    def __repr__(self):
        return f'<IncomeOrder {self.code}: {self.status}>'
    
    @property
    def unreceived_amount(self):
        """未收款金额"""
        return float(self.total_amount) - float(self.received_amount)
    
    def update_received_amount(self):
        """更新已收款金额和状态（统计所有状态的收款单分录）"""
        from app.models.receipt_order import ReceiptOrder
        total_received = db.session.query(db.func.sum(ReceiptOrderLine.amount)).\
            filter(ReceiptOrderLine.income_order_id == self.id).scalar() or 0
        
        self.received_amount = total_received
        
        # 更新状态
        if float(self.received_amount) >= float(self.total_amount):
            self.status = self.STATUS_FULL_RECEIVED
        elif float(self.received_amount) > 0:
            self.status = self.STATUS_PART_RECEIVED
        elif self.status in [self.STATUS_PART_RECEIVED, self.STATUS_FULL_RECEIVED]:
            self.status = self.STATUS_AUDITED
        
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'order_date': self.order_date.strftime('%Y-%m-%d') if self.order_date else None,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name if self.customer else None,
            'status': self.status,
            'total_amount': float(self.total_amount),
            'received_amount': float(self.received_amount),
            'unreceived_amount': self.unreceived_amount,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
    
    def get_receipt_details(self):
        """获取收款明细"""
        from app.models.receipt_order import ReceiptOrder
        details = []
        for line in self.receipt_lines:
            receipt = line.receipt_order
            if receipt and receipt.status == ReceiptOrder.STATUS_AUDITED:
                details.append({
                    'receipt_code': receipt.code,
                    'receipt_date': receipt.order_date.strftime('%Y-%m-%d') if receipt.order_date else None,
                    'amount': float(line.amount),
                    'account_name': receipt.account.name if receipt.account else None
                })
        return details


class IncomeOrderLine(db.Model):
    __tablename__ = 'income_order_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('income_orders.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('income_categories.id'), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<IncomeOrderLine {self.id}: {self.amount}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'category_code': self.category.code if self.category else None,
            'amount': float(self.amount),
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

# 避免循环导入
from app.models.receipt_order import ReceiptOrderLine
