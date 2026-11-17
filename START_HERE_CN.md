# Goodwill Pricing — Module 2 使用说明

本次是在已经运行成功的 Module 1 上增加 Pricing Guideline Management。
代码包包含完整的 Module 1 和 Module 2；保留原项目作为备份即可。

## 1. 更新原项目（推荐）

停止正在运行的 Streamlit：在原 Terminal 窗口按 `Control + C`。

解压 `goodwill_module2.zip`，把下面的文件复制到原 `goodwill_module1` 项目中的对应位置：

| 文件 | 操作 | 用途 |
| --- | --- | --- |
| `app.py` | 替换原文件 | 加入管理员导航及定价指南页面 |
| `guidelines.py` | 新增到项目根目录 | 查询、保存、检查权限及业务规则 |
| `guideline_page.py` | 新增到项目根目录 | 列表、筛选、新增和编辑表单 |
| `scripts/check_module2.py` | 新增到 `scripts` 文件夹 | 只读检查数据库结构和重复指南 |
| `tests/test_guidelines.py` | 新增到 `tests` 文件夹 | 后台业务规则测试 |
| `tests/test_guideline_page.py` | 新增到 `tests` 文件夹 | Streamlit 表单和权限测试 |
| `.streamlit/config.toml` | 可选：复制到 `.streamlit` | 白底、蓝色主题 |

保留你原来的 `.streamlit/secrets.toml`、`auth.py` 和 `database.py`。
本次依赖与 Module 1 相同，不需要修改已有数据库连接参数。

在原项目文件夹中，继续使用之前的 Python 环境：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.check_module2
python -m streamlit run app.py
```

如果原来已经激活 Python 环境，可跳过第一行。`check_module2` 不插入、修改或删除任何数据。
如果使用不同名称的虚拟环境，沿用原来的激活命令。

## 2. 或者使用完整的新文件夹

进入解压后的 `goodwill_module2` 文件夹，创建 Python 环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

把原项目已配置好的 `.streamlit/secrets.toml` 复制到新项目的 `.streamlit` 文件夹。
macOS Finder 按 `Command + Shift + .` 可以显示隐藏文件夹。
只在你自己的电脑复制数据库配置，不要把该文件发给别人。

然后执行：

```bash
python -m scripts.check_module2
python -m streamlit run app.py
```

## 3. 登录后如何使用

1. 使用原来的管理员 Username 和 Password 登录。
2. 左侧选择 `Pricing Guidelines`。
3. `Browse & Edit`：查看列表，按名称/ID搜索，筛选 Active/Inactive。
4. `Add Guideline`：选择 Category、Brand、Condition、Item Type，输入价格，点击 `Save New Guideline`。
5. 编辑：在 `Select guideline to edit` 选择记录，修改后点 `Save Changes`。
6. 状态：点击 `Deactivate Guideline` 停用；点击 `Activate Guideline` 恢复。

输入价格示例：`12.99`，不要输入美元符号。价格必须大于零，最多两位小数，最大为 `999999.99`。

四组下拉选项来自现有 CATEGORY、BRAND、ITEM_CONDITION、ITEM_TYPE 表。
如果基础表没有记录，页面会提示先补充相应数据。此模块不包含基础资料、用户或门店维护页面。

## 4. 保存规则

| 情况 | 系统行为 |
| --- | --- |
| 新增指南 | 程序生成 Guideline_Id，写入当前管理员 ID 和数据库时间 |
| 相同四项属性已有 Active 指南 | 阻止新增/恢复冲突的 Active 指南 |
| 相同属性的 Inactive 指南 | 允许保留多个历史记录 |
| 修改价格或四项属性 | 在一个事务中停用旧记录并新增记录，返回新的 Guideline_Id |
| 只改变 Active 状态 | 更新原记录状态及更新时间 |
| 其他管理员修改了当前打开的记录 | 拒绝覆盖，提示点 `Reload selected guideline` 重新加载 |
| 保存过程中出错 | 回滚本次事务，包括已执行的旧记录停用操作 |

例如：原指南 #8 为 `$12.99`，改成 `$15.99` 后，系统新增指南 #9，并把 #8 设为 Inactive。
已存在的 PRICING_DECISION 仍然关联 #8，因此仍能看到当时的建议价格。
不执行物理删除；历史记录不会因为修改指南而丢失。

本次直接使用现有 G3 数据库，不需要重新运行建表 SQL，也不要删除已有数据。
MySQL 登录账户需要相关表的 SELECT 权限，以及 PRICING_GUIDELINE 的 INSERT、UPDATE 权限。

## 5. 本机验证顺序

建议使用项目测试数据库进行以下操作：

1. 管理员登录，确认四个下拉菜单出现真实数据库选项。
2. 用尚无 Active 指南的四项组合新增一条指南。
3. 再新增相同组合，确认页面阻止重复 Active 指南。
4. 修改价格，确认旧记录变为 Inactive，新记录使用新 ID。
5. 停用并恢复新记录，确认列表状态正确。
6. 用员工账户登录，确认只显示员工主页，没有管理员指南管理入口。

本地自动测试：

```bash
python -m unittest discover -s tests -v
```

已在 Python 3.12 / Streamlit 1.67.0 / mysql-connector-python 9.7.0 / bcrypt 4.3.0 环境通过 28 项测试。
后台测试使用模拟数据库连接；页面测试使用 Streamlit AppTest。未连接你的实际 MySQL 服务器。
`check_module2` 只检查读取、字段、InnoDB 和重复指南，不验证实际写入权限。

## 6. 当前实现边界

- 程序利用 MySQL `GET_LOCK` 串行化本模块写入，再分配递增整数 ID、检查 Active 指南唯一性。锁不是数据库唯一约束；直接在 Workbench 或其他程序写入可能绕过这些检查。
- 该锁适合当前单 MySQL 实例项目。所有指南写入都应使用同一套服务函数。
- 当前表没有完整审计字段或版本链。旧价格/属性会保留，但不能完整列出每次状态切换的操作者及时间。
- 时间来自 MySQL `NOW()`，页面显示数据库服务器的时间；金额按美元显示。
- 本模块不包含员工商品录入、价格匹配、最终定价和条码打印；它们是后续模块。

下一步：Module 3 — Item Entry & Price Matching。
