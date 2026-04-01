# ERP资金管理系统 测试BUG记录

> 项目：ERP资金管理系统（arPython）  
> 测试阶段：验收测试（erp-fund-acceptance） + 开发自测（erp-unit-test） + QA专家测试（erp-qa-expert）  
> 文档维护：测试团队

---

## 第一阶段：功能验收测试发现的问题（erp-fund-acceptance）

> 测试方式：人工验收，基于需求规范逐项验证功能完整性

---

### BUG-ACC-001：其他收入单反审核无响应（P0 严重）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（核心功能不可用） |
| **发现方式** | 验收步骤3，点击反审核按钮无任何提示和状态变更 |
| **现象** | 其他收入单已审核后，点击反审核按钮无响应，状态不更新，无任何提示 |
| **根因** | `income_order.py` 反审核路由中使用了 `ReceiptOrderLine`，但该模型未在模块顶部导入（仅在函数内部局部导入），导致逻辑执行时引用异常 |
| **修复方案** | 将 `ReceiptOrderLine` 导入移至模块顶部，移除函数内部重复导入 |
| **修复文件** | `app/routes/income_order.py` |
| **状态** | ✅ 已修复 |

---

### BUG-ACC-002：收款单缺少审核、反审核、批量操作功能（P0 严重）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（核心功能缺失） |
| **发现方式** | 验收步骤4，收款单列表无审核/反审核/批量操作入口 |
| **现象** | 收款单列表和详情页均未提供审核、反审核按钮；无批量操作栏 |
| **根因** | 功能未实现，路由和前端均缺失 |
| **修复方案** | 新增 `unaudit_order` 和 `batch_operation` 路由；更新 `receipt_order/list.html`，添加批量操作栏和状态条件按钮（未审核显示审核/删除，已审核显示反审核） |
| **修复文件** | `app/routes/receipt_order.py`、`app/templates/receipt_order/list.html` |
| **状态** | ✅ 已修复 |

---

### BUG-ACC-003：其他收入单列表批量复制按钮不应存在（P2）

| 属性 | 内容 |
|------|------|
| **严重级别** | P2（与需求规范不符） |
| **发现方式** | 验收步骤3，需求规范明确批量操作不含复制 |
| **现象** | 其他收入单列表批量操作栏存在"批量复制"按钮，需求规范明确不支持批量复制 |
| **根因** | 开发阶段未严格按需求规范控制按钮范围 |
| **修复方案** | 从 `list.html` 批量操作栏中移除批量复制按钮 |
| **修复文件** | `app/templates/income_order/list.html` |
| **状态** | ✅ 已修复 |

---

### BUG-ACC-004：其他收入单列表审核状态与收款状态未分列展示（P2）

| 属性 | 内容 |
|------|------|
| **严重级别** | P2（列表展示与需求规范不符） |
| **发现方式** | 验收步骤3，需求要求审核状态和收款状态独立展示 |
| **现象** | 列表仅有一列"收款状态"，审核状态与收款状态混合展示，未按需求分为两个独立列 |
| **根因** | 列表模板未拆分两列 |
| **修复方案** | 在 `income_order/list.html` 新增独立的"审核状态"列（黄色"未审核"、绿色"已审核"），"收款状态"列改为展示收款维度信息（灰色"-"、蓝色"未收款"、黄色"部分收款"、绿色"全部收款"） |
| **修复文件** | `app/templates/income_order/list.html` |
| **状态** | ✅ 已修复 |

---

### BUG-ACC-005：收款单列表"单据状态"列位置错误（P3）

| 属性 | 内容 |
|------|------|
| **严重级别** | P3（UI规范不一致） |
| **发现方式** | 验收步骤4，列顺序与需求规范及其他模块不统一 |
| **现象** | 收款单列表"单据状态"列位于最后一列，应位于复选框之后、单据编号之前 |
| **根因** | 列顺序未按规范排列 |
| **修复方案** | 在 `receipt_order/list.html` 的 `<thead>` 和 `<tbody>` 中，将"单据状态"列同步移至复选框列之后 |
| **修复文件** | `app/templates/receipt_order/list.html` |
| **状态** | ✅ 已修复 |

---

### BUG-ACC-006：收款单保存时不更新收入单状态；审核时错误触发反写（P0 严重）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（核心业务逻辑错误） |
| **发现方式** | 验收步骤4，保存收款单后收入单收款状态无变化 |
| **现象** | 保存收款单后收入单已收款金额/收款状态不更新；审核收款单时错误触发收入单状态反写 |
| **根因** | 反写逻辑绑定在审核操作上，而非保存操作上；`update_received_amount()` 只统计已审核收款单 |
| **修复方案** | 将反写逻辑从 audit/unaudit 移至 create/edit 路由；在保存后直接累加金额并更新收入单状态；移除 audit/unaudit 对收入单的反写逻辑 |
| **修复文件** | `app/routes/receipt_order.py`、`app/models/income_order.py` |
| **状态** | ✅ 已修复 |

---

### BUG-ACC-007：选择源单弹窗未过滤已全部收款的收入单（P1）

| 属性 | 内容 |
|------|------|
| **严重级别** | P1（影响数据准确性） |
| **发现方式** | 验收步骤4，弹窗中出现已全部收款的收入单 |
| **现象** | 新建收款单时选择源单弹窗显示了已全部收款的收入单，应过滤掉 |
| **根因** | `api_available_orders` 接口未过滤 `unreceived_amount <= 0` 的单据 |
| **修复方案** | 在 `api_available_orders` 中增加过滤条件，只返回 `unreceived_amount > 0` 的已审核收入单；同时补充返回 `audit_status`、`receipt_status` 字段与列表保持一致 |
| **修复文件** | `app/routes/income_order.py` |
| **状态** | ✅ 已修复 |

---

## 第二阶段：开发单元测试发现的问题（erp-unit-test）

> 测试文件：`tests/test_erp.py`（31个用例）  
> 测试方式：白盒测试，Flask test_client + SQLite内存数据库

### BUG-ENV-001：测试环境 UNIQUE constraint 冲突

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（环境问题，阻塞所有测试执行） |
| **发现方式** | 运行测试时报错 |
| **现象** | `UNIQUE constraint failed: accounts.code` 导致全量测试失败 |
| **根因** | `create_app()` 内部调用 `init_all_data()` 已插入 `ZH001` 等基础数据，测试 fixture 的 `_seed_data()` 再次插入相同 code 的数据造成冲突 |
| **修复方案** | fixture 改为 `session` scope（整个测试共享一个app实例）；seed 数据改用 `T_` 前缀（如 `T_KH001`、`T_SR001`、`T_ZH001`）避免与 `init_all_data()` 数据冲突 |
| **修复文件** | `tests/test_erp.py` |
| **状态** | ✅ 已修复 |

---

### BUG-ENV-002：客户创建接口表单/JSON类型不匹配

| 属性 | 内容 |
|------|------|
| **严重级别** | P2（接口行为与预期不符） |
| **发现方式** | `test_create_customer_success` 失败，`success=False` |
| **现象** | 测试发送 JSON 数据，但路由使用 `request.form.get('name')` 读取表单字段，导致 name 为 None，创建失败 |
| **根因** | `/customer/create` 路由设计为接收 HTML form 提交，而非 JSON 接口 |
| **修复方案** | 测试改为使用 `client.post('/customer/create', data={'name': '...'})` 表单方式提交 |
| **修复文件** | `tests/test_erp.py` |
| **状态** | ✅ 已修复 |

---

## 第二阶段：QA专家测试发现的BUG（erp-qa-expert）

> 测试文件：`tests/test_erp_qa.py`（57个用例）  
> 测试方式：灰盒测试，应用8种测试用例设计方法

---

### BUG-001：编辑收款单后金额叠加（P0 严重）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（数据一致性核心BUG） |
| **测试方法** | 错误推测法 + 因果图法 |
| **测试用例** | `TestP0EditReceiptWriteback::test_edit_receipt_increases_amount_correctly` |
| **复现步骤** | 1. 创建收入单（总额200）→ 审核 → 创建收款单（收款60）→ 编辑收款单（改为80） |
| **预期结果** | 收入单已收款金额 = 80 |
| **实际结果** | 收入单已收款金额 = 140（60+80，旧金额未回退） |
| **根因** | `edit_order` 逻辑：先删除旧分录，再插入新分录并累加金额，未在删除前先回退旧分录关联收入单的已收款金额 |
| **修复方案** | 在删除旧分录前，遍历旧分录逐一回退关联收入单的 `received_amount`，再重新计算状态 |
| **修复文件** | `app/routes/receipt_order.py`（edit_order 函数） |
| **修复代码片段** | `old_income.received_amount = max(Decimal('0'), Decimal(str(old_income.received_amount)) - Decimal(str(old_line.amount)))` |
| **状态** | ✅ 已修复 |

---

### BUG-002：编辑收款单减少金额后状态错误（P0 严重）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（数据一致性核心BUG） |
| **测试方法** | 错误推测法 |
| **测试用例** | `TestP0EditReceiptWriteback::test_edit_receipt_decreases_amount_correctly` |
| **复现步骤** | 创建收入单（总额200）→ 审核 → 创建收款单（100）→ 编辑收款单（改为40） |
| **预期结果** | 已收款金额 = 40，状态 = 部分收款 |
| **实际结果** | 已收款金额 = 140，状态 = 部分收款（数值错误） |
| **根因** | 与 BUG-001 同源：edit_order 未先回退旧金额 |
| **修复方案** | 同 BUG-001 |
| **修复文件** | `app/routes/receipt_order.py` |
| **状态** | ✅ 已修复 |

---

### BUG-003：编辑收款单至全额后状态未变为"全部收款"（P0 严重）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（状态判断依赖错误金额） |
| **测试方法** | 边界值分析 + 错误推测法 |
| **测试用例** | `TestP0EditReceiptWriteback::test_edit_receipt_to_full_amount_changes_status` |
| **复现步骤** | 创建收入单（总额100）→ 审核 → 创建收款单（50）→ 编辑收款单（改为100） |
| **预期结果** | 已收款金额 = 100，状态 = 全部收款 |
| **实际结果** | 已收款金额 = 150，状态判断异常 |
| **根因** | 同 BUG-001 |
| **修复方案** | 同 BUG-001 |
| **修复文件** | `app/routes/receipt_order.py` |
| **状态** | ✅ 已修复 |

---

### BUG-004：批量删除收款单后关联收入单金额不回退（P0 严重）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（数据一致性核心BUG） |
| **测试方法** | 流程分析法 + 错误推测法 |
| **测试用例** | `TestP0DataConsistency::test_batch_delete_receipts_all_rollback` |
| **复现步骤** | 创建两张收入单和各自的收款单 → 批量删除两张收款单 |
| **预期结果** | 两张收入单的 received_amount = 0，状态 = 已审核 |
| **实际结果** | received_amount 不变，状态不回退 |
| **根因** | `batch_operation` 中 delete 分支直接使用 `db.session.delete(order)`，绕过了 `order.delete()` 方法中封装的金额回退逻辑 |
| **修复方案** | 改为调用 `success, _ = order.delete()` 以复用回退逻辑 |
| **修复文件** | `app/routes/receipt_order.py`（batch_operation 函数） |
| **修复代码片段** | `success, _ = order.delete()` |
| **状态** | ✅ 已修复 |

---

### BUG-005：收款金额为0时错误提示"分录信息不完整"（P1）

| 属性 | 内容 |
|------|------|
| **严重级别** | P1（提示信息错误，影响用户体验） |
| **测试方法** | 边界值分析 + 等价类划分 |
| **测试用例** | `TestP1BoundaryValues::test_receipt_amount_zero_rejected` |
| **复现步骤** | 创建收款单，分录金额填写 0 |
| **预期结果** | 返回失败，提示"金额必须大于0" |
| **实际结果** | 返回失败，提示"分录信息不完整"（提示不准确） |
| **根因** | 代码使用 `if not amount` 判断，Python 中 `not 0 == True`，将 amount=0 误判为"未填写"而非"金额不合法" |
| **修复方案** | 将 `if not amount` 改为 `if amount is None`，再单独校验 `if amount <= 0` 返回"金额必须大于0" |
| **修复文件** | `app/routes/receipt_order.py`、`app/routes/income_order.py` |
| **修复代码片段** | `if not income_order_id or amount is None:` |
| **状态** | ✅ 已修复 |

---

### BUG-006：update_received_amount 只统计已审核收款单（P0 隐性BUG）

| 属性 | 内容 |
|------|------|
| **严重级别** | P0（影响金额回退计算） |
| **测试方法** | 因果图法 |
| **测试用例** | `TestP0DataConsistency::test_delete_partial_receipt_rollback_to_audited` |
| **复现步骤** | 创建收入单 → 审核 → 创建未审核收款单 → 删除收款单（触发 update_received_amount） |
| **预期结果** | 收入单 received_amount = 0，状态回退为已审核 |
| **实际结果** | received_amount 回退为 0（正确），但原方法中的 filter 导致在某些流程下计算不准确 |
| **根因** | `update_received_amount()` 内部有 `.filter(ReceiptOrder.status == AUDITED)` 过滤，只统计已审核收款单金额；但收款单保存时处于未审核状态，删除时重新计算得 0，虽结果偶然正确，但逻辑隐患会在其他场景导致金额错误 |
| **修复方案** | 移除 `.filter(ReceiptOrder.status == ReceiptOrder.STATUS_AUDITED)` 限制，改为统计所有状态的收款单分录金额 |
| **修复文件** | `app/models/income_order.py`（update_received_amount 方法） |
| **状态** | ✅ 已修复 |

---

## BUG汇总统计

| 阶段 | BUG编号 | 严重级别 | 分类 | 状态 |
|------|---------|---------|------|------|
| 功能验收 | BUG-ACC-001 | P0 | 反审核无响应（导入缺失） | ✅ 已修复 |
| 功能验收 | BUG-ACC-002 | P0 | 收款单审核/反审核/批量功能缺失 | ✅ 已修复 |
| 功能验收 | BUG-ACC-003 | P2 | 批量复制按钮不符需求规范 | ✅ 已修复 |
| 功能验收 | BUG-ACC-004 | P2 | 审核状态与收款状态未分列 | ✅ 已修复 |
| 功能验收 | BUG-ACC-005 | P3 | 收款单列表列顺序错误 | ✅ 已修复 |
| 功能验收 | BUG-ACC-006 | P0 | 反写绑定审核而非保存，逻辑错误 | ✅ 已修复 |
| 功能验收 | BUG-ACC-007 | P1 | 源单弹窗未过滤已全部收款单据 | ✅ 已修复 |
| 开发自测 | BUG-ENV-001 | P0 | 测试环境问题 | ✅ 已修复 |
| 开发自测 | BUG-ENV-002 | P2 | 接口类型不匹配 | ✅ 已修复 |
| QA专家测试 | BUG-001 | P0 | 编辑金额叠加 | ✅ 已修复 |
| QA专家测试 | BUG-002 | P0 | 编辑金额叠加（减少方向） | ✅ 已修复 |
| QA专家测试 | BUG-003 | P0 | 编辑至全额状态未更新 | ✅ 已修复 |
| QA专家测试 | BUG-004 | P0 | 批量删除不回退金额 | ✅ 已修复 |
| QA专家测试 | BUG-005 | P1 | amount=0 提示不准确 | ✅ 已修复 |
| QA专家测试 | BUG-006 | P0 | update_received_amount 过滤逻辑隐患 | ✅ 已修复 |

**P0 BUG：9个（全部已修复）**  
**P1 BUG：2个（全部已修复）**  
**P2 BUG：3个（全部已修复）**  
**P3 BUG：1个（全部已修复）**  
**当前状态：全量 88/88 测试通过（31个单元测试 + 57个QA测试）**

---

## 防回归说明

以下是高风险改动点，后续开发时需重点关注：

1. **编辑收款单逻辑**：每次修改 `edit_order`，必须确保"先回退旧金额，再写入新金额"的两步操作完整保留
2. **批量操作删除**：`batch_operation` 中的 delete 分支必须通过 `order.delete()` 方法执行，不可直接 `db.session.delete(order)`
3. **金额合法性校验**：对金额字段的 falsy 判断必须区分 `None`（未传值）和 `0`（传了但不合法），不可简写为 `if not amount`
4. **update_received_amount 范围**：该方法必须统计所有状态的收款单分录，不可加状态过滤条件
