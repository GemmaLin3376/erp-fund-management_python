import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'database', 'erp.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 数据库连接池优化
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # 连接前 ping 检测，避免使用失效连接
        'pool_recycle': 3600,   # 1小时后回收连接
    }
    
    # 静态文件缓存
    SEND_FILE_MAX_AGE_DEFAULT = 86400  # 静态文件缓存1天
    
    PER_PAGE_DEFAULT = 5
