from app import db

class CodeGenerator:
    """编码生成器"""
    
    PREFIXES = {
        'customer': 'KH',
        'income_category': 'SR',
        'account': 'ZH',
        'income_order': 'SRD',
        'receipt_order': 'SKD'
    }
    
    @classmethod
    def generate_code(cls, model_class, prefix_key):
        """
        生成编码
        :param model_class: 模型类
        :param prefix_key: 前缀键
        :return: 生成的编码
        """
        prefix = cls.PREFIXES.get(prefix_key, 'XX')
        
        # 查询最大编码
        last_record = model_class.query.order_by(model_class.id.desc()).first()
        
        if last_record and last_record.code:
            # 提取数字部分
            try:
                num_part = int(last_record.code[len(prefix):])
                new_num = num_part + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        # 格式化为3位数字
        return f"{prefix}{new_num:03d}"
