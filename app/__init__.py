from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 启用模板缓存（生产环境）
    app.jinja_env.auto_reload = False
    app.config['TEMPLATES_AUTO_RELOAD'] = False
    
    db.init_app(app)
 
    from app.routes import customer, income_category, account, income_order, receipt_order, main
    
    app.register_blueprint(main.bp)
    app.register_blueprint(customer.bp, url_prefix='/customer')
    app.register_blueprint(income_category.bp, url_prefix='/income_category')
    app.register_blueprint(account.bp, url_prefix='/account')
    app.register_blueprint(income_order.bp, url_prefix='/income_order')
    app.register_blueprint(receipt_order.bp, url_prefix='/receipt_order')
    
    with app.app_context():
        db.create_all()
        from app.utils.init_data import init_all_data
        init_all_data()
    
    return app
