# PythonAnywhere 部署指南

## 第一步：注册账号
1. 访问 https://www.pythonanywhere.com
2. 点击 "Start running Python online in less than a minute"
3. 填写用户名、邮箱、密码注册
4. 邮箱验证（查收验证邮件）

## 第二步：创建 Web 应用

登录后点击 **"Web"** 标签 → **"Add a new web app"**

选择：
- **Flask**
- **Python 3.10**（或最新版）
- 保持默认路径，点击 Next

## 第三步：配置项目

在 PythonAnywhere 的 Bash 控制台执行：

```bash
# 1. 克隆代码（替换为你的GitHub地址）
cd ~
git clone https://github.com/GemmaLin3376/erp-fund-management_python.git

# 2. 进入项目目录
cd erp-fund-management_python

# 3. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

## 第四步：修改 WSGI 配置

点击 **"Web"** 标签 → 找到你的应用 → **"WSGI configuration file"**

删除原有内容，替换为：

```python
import sys
path = '/home/你的用户名/erp-fund-management_python'
if path not in sys.path:
    sys.path.insert(0, path)

from app import create_app
application = create_app()
```

## 第五步：配置静态文件（可选）

在 Web 配置页面：
- **Static files**: 添加
  - URL: `/static/`
  - Directory: `/home/你的用户名/erp-fund-management_python/app/static`

## 第六步：重启应用

点击 **"Reload"** 按钮

## 访问地址

你的应用将在以下地址访问：
```
https://你的用户名.pythonanywhere.com
```

## 注意事项

1. **免费版限制**：
   - 每天需要手动点击 "Reload" 重启（或设置定时任务）
   - 不能绑定自定义域名
   - 有 CPU/内存使用限制

2. **数据库**：
   - SQLite 数据库在项目目录下，会被保留
   - 如果需要 MySQL，需要升级到付费版

3. **文件修改**：
   - 代码更新后需要点击 "Reload" 生效
   - 也可以在 Bash 中执行 `git pull` 拉取最新代码

## 更新代码命令

```bash
cd ~/erp-fund-management_python
git pull
# 然后点击 Web 页面的 Reload 按钮
```
