from app import db
from app.models import Customer, IncomeCategory, Account

def init_customers():
    """初始化客户数据"""
    if Customer.query.count() == 0:
        customers = [
            Customer(code='KH001', name='XX科技有限公司'),
            Customer(code='KH002', name='XX贸易有限公司'),
            Customer(code='KH003', name='XX服务有限公司')
        ]
        for customer in customers:
            db.session.add(customer)
        db.session.commit()
        print("客户数据初始化完成")

def init_income_categories():
    """初始化收入类别数据"""
    if IncomeCategory.query.count() == 0:
        categories = [
            IncomeCategory(code='SR001', name='服务费'),
            IncomeCategory(code='SR002', name='销售款'),
            IncomeCategory(code='SR003', name='其他杂项收入')
        ]
        for category in categories:
            db.session.add(category)
        db.session.commit()
        print("收入类别数据初始化完成")

def init_accounts():
    """初始化收款账户数据"""
    if Account.query.count() == 0:
        accounts = [
            Account(code='ZH001', name='工商银行XX支行'),
            Account(code='ZH002', name='建设银行XX支行')
        ]
        for account in accounts:
            db.session.add(account)
        db.session.commit()
        print("收款账户数据初始化完成")

def init_all_data():
    """初始化所有数据"""
    init_customers()
    init_income_categories()
    init_accounts()
