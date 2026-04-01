"""
冒烟测试 - 针对实际运行中的HTTP服务
验证所有页面可访问，无500错误
"""
import pytest
import requests

BASE_URL = "http://127.0.0.1:5001"


class TestSmokePages:
    """冒烟测试：验证所有页面可访问"""

    def test_home_page(self):
        """首页可访问"""
        resp = requests.get(f"{BASE_URL}/")
        assert resp.status_code == 200
        assert "ERP" in resp.text or "资金" in resp.text

    def test_customer_list_page(self):
        """客户列表页可访问"""
        resp = requests.get(f"{BASE_URL}/customer/")
        assert resp.status_code == 200
        assert "客户" in resp.text

    def test_income_category_page(self):
        """收入类别页可访问"""
        resp = requests.get(f"{BASE_URL}/income_category/")
        assert resp.status_code == 200
        assert "收入类别" in resp.text or "类别" in resp.text

    def test_account_page(self):
        """收款账户页可访问"""
        resp = requests.get(f"{BASE_URL}/account/")
        assert resp.status_code == 200
        assert "账户" in resp.text

    def test_income_order_list_page(self):
        """其他收入单列表页可访问"""
        resp = requests.get(f"{BASE_URL}/income_order/")
        assert resp.status_code == 200
        assert "其他收入单" in resp.text or "收入单" in resp.text

    def test_income_order_create_page(self):
        """其他收入单新增页可访问"""
        resp = requests.get(f"{BASE_URL}/income_order/create")
        assert resp.status_code == 200

    def test_receipt_order_list_page(self):
        """收款单列表页可访问"""
        resp = requests.get(f"{BASE_URL}/receipt_order/")
        assert resp.status_code == 200
        assert "收款单" in resp.text

    def test_receipt_order_create_page(self):
        """收款单新增页可访问"""
        resp = requests.get(f"{BASE_URL}/receipt_order/create")
        assert resp.status_code == 200

    def test_no_operational_error(self):
        """关键页面不应出现OperationalError"""
        pages = [
            "/",
            "/customer/",
            "/income_category/",
            "/account/",
            "/income_order/",
            "/receipt_order/",
        ]
        for page in pages:
            resp = requests.get(f"{BASE_URL}{page}")
            assert resp.status_code == 200, f"{page} 返回 {resp.status_code}"
            assert "OperationalError" not in resp.text, f"{page} 出现数据库错误"
            assert "no such table" not in resp.text, f"{page} 表不存在"
