# Goodwill Pricing：部署到 Aiven，实现公网访问

适用版本：Module 1 + Module 2；说明核对日期：2026-11-17。

这个文件夹包含完整应用代码，以及新增的 Dockerfile、.dockerignore 和支持云端环境变量的 database.py。
部署前，仍需准备你的 Aiven MySQL 数据库、CA 证书和 GitHub 仓库。

## 1. 两个服务各负责什么

| 组件 | 放在哪里 | 用途 |
| --- | --- | --- |
| Python / Streamlit 应用 | Aiven Runtime | 运行 app.py、登录页面、管理页面和业务逻辑 |
| 11 张表及记录 | Aiven for MySQL | 保存账户、分类、指南和定价记录 |
| 源代码 | GitHub 仓库 | Aiven 拉取代码、构建容器的来源 |

这是一个 Streamlit 应用，页面和 Python 业务逻辑在同一个进程运行；当前没有单独的 REST API。
Runtime 提供可以用浏览器访问的 HTTPS 地址。只有数据库服务并不会产生应用网页。
应用和数据库分别选择套餐；部署前在 Aiven 控制台确认各自费用。本文没有创建或购买云服务。

## 2. 准备 MySQL 数据库

如果你的项目数据库已经在 Aiven，沿用现有服务即可，不要重复创建或导入。

如果数据库还在学校/原服务器：

1. 打开 https://console.aiven.io/ ，进入项目。
2. 选择 Services → Create service → MySQL，选择可用云区域和套餐。
3. 等待服务状态为 Running。
4. 从 Overview → Connection information 获取 Host、Port、User、Password，并下载 CA Certificate。
5. 将下载的 CA 证书命名为 `ca.pem`，放在这个项目文件夹根目录，与 `app.py` 同级。
6. 使用 MySQL Workbench 连接 Aiven。Host 和 Port 必须照控制台填写；在 SSL 设置中选择下载的 CA 证书，并启用服务器证书验证。
7. 在 Aiven 创建目标数据库，建议沿用当前数据库名；把原数据库的结构和数据一起导入，包括 11 张表和管理员记录。导入前核对 SQL 中的 CREATE DATABASE / USE 指向目标数据库。

仅执行原来的建表脚本不能恢复用户数据。请从当前数据库导出结构和数据，而不是只复制 CREATE TABLE。
也不要把包含 DROP TABLE 的 G3 脚本设置为每次启动自动执行。

应用的 MySQL 服务用户需要 SELECT 权限，以及后续业务所需的 INSERT / UPDATE 权限。`MYSQL_USER` 是数据库连接用户，不是应用登录用户名 `kwhitfield`。

## 3. 上传代码到 GitHub

1. 创建一个仓库，例如 `goodwill-pricing`。可以使用 Private 仓库并授权 Aiven 读取该仓库。
2. 上传本文件夹里面的内容，确保 `Dockerfile`、`app.py`、`requirements.txt` 和 `ca.pem` 在仓库根目录。
3. 包含 `.streamlit/config.toml`，保留 `.gitignore` 与 `.dockerignore`。

不要直接上传 ZIP；Runtime 需要读取解压后的源码。
不要上传真实 `.streamlit/secrets.toml`、`.env`、数据库备份、数据库密码或私钥。`.gitignore` 不会保护浏览器手动上传时主动选择的文件，所以手动选文件时同样要排除它们。
`ca.pem` 应当是从 Aiven 下载的 CA 公共证书，不是私钥。

如果你在 Mac 上看不到点号开头的文件，可以在 Finder 按 Command + Shift + .。

## 4. 在 Aiven 部署应用

1. 进入 Aiven 项目，打开 Runtime。
2. 点击 Deploy application。
3. 连接 GitHub，选中上面的 Repository 和 Branch。
4. 点击 Next，选择根目录的 `Dockerfile`，点击 Scan。
5. 应用名称可填 `goodwill-pricing`。
6. 确认容器端口是 `8501`，协议是 `HTTP`；应用套餐以控制台实际显示的价格为准。
7. 如果部署配置中提供环境变量入口，先填下一节的变量；否则部署后立即到应用 Overview → Environment variables → Edit 填写。
8. 点击 Deploy，查看构建日志和运行状态。

Dockerfile 会安装 requirements.txt，并运行：

```bash
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
```

GitHub 仓库需要授权给当前 Aiven 组织。如果没有 Runtime 或无法部署，请检查组织/项目权限和控制台服务可用情况；不要在 MySQL 的数据导入页面上传 Python 文件。

## 5. 设置应用环境变量

在 Runtime 应用的 Overview → Environment variables → Edit 中添加：

| 名称 | 填写内容 |
| --- | --- |
| `MYSQL_HOST` | Aiven MySQL 的完整 Host |
| `MYSQL_PORT` | Aiven MySQL 的 Port，例如控制台实际给出的端口，不要直接假定为 3306 |
| `MYSQL_USER` | Aiven MySQL 数据库连接用户 |
| `MYSQL_PASSWORD` | 上述数据库用户密码，标记为 Secret |
| `MYSQL_DATABASE` | 已导入 11 张表的数据库名，大小写与数据库一致 |
| `MYSQL_SSL_CA` | `/app/ca.pem` |

这些 `MYSQL_*` 名称是此代码包定义的手动配置接口，不是假设 Aiven 自动生成这些变量。
如果使用 Aiven 的 Connected services，仍需检查其提供的变量格式；本代码包采用上面的单独变量，不读取服务 URI。

填写后保存。Aiven 会用新的变量重新部署应用。第一次还没填变量时，登录页面可以显示，但提交登录会失败。

云端配置只要检测到任一 MYSQL_HOST / PORT / USER / PASSWORD / DATABASE 变量，就要求五个全部填写，避免混用本地和云端数据库配置。
云端连接强制 TLS，校验证书和主机名。缺少 CA 文件时会报错，不会降级到未验证连接。

## 6. 获取公网地址并测试

1. 打开 Runtime 应用的 Overview → Connection information。
2. 找到 Aiven 提供的应用域名/HTTPS 地址，用浏览器打开。
3. 外部访问走 HTTPS 443；Aiven 把请求转发到容器内部的 HTTP 8501。因此给组员的是应用 HTTPS 地址，不是数据库 Host:Port。
4. 用数据库中已经修复为 bcrypt 密码的管理员账户登录。
5. 检查能否查看指南，再在项目测试数据中验证新增和停用。
6. 确认后把应用地址发给需要测试的组员；他们使用各自的应用账户登录。

账户问题与部署问题应分开排查。此前截图中密码哈希不是当前登录代码要求的 bcrypt，需要先按之前的步骤修复。
截图中员工 User_Type 为 `Store Staff`，现有程序识别 `Employee`；本部署包没有改变角色设计，该差异仍须统一后才能用员工账户登录。

如果连接超时，请检查 MySQL 服务网络策略是否允许 Runtime 应用连接。网页公开不意味着要关闭数据库认证或证书校验。

## 7. 更新代码与本地运行

修改代码并推送 GitHub 后，进入 Runtime 应用 → Actions → Deploy latest commit。
Aiven 当前不会因为 GitHub push 自动部署新版本；修改环境变量也只会重新部署此前版本。

本地仍可使用原来的 `.streamlit/secrets.toml`。如果本地没有 MYSQL_* 云端变量，代码沿用原来的配置方式。

```bash
python -m scripts.check_module2
python -m streamlit run app.py
```

要在本机先验证 Aiven 连接，把本地 secrets.toml 的 host、port、user、password、database 改为 Aiven 参数，并在同一 [mysql] 段加入：

```toml
ssl_ca = "ca.pem"
ssl_verify_cert = true
ssl_verify_identity = true
```

## 验证范围

35 项本地测试通过：原有 28 项，以及新增 7 项云端配置测试。测试覆盖环境变量选择、端口解析、缺少证书时拒绝连接、本地配置兼容和 TLS 校验参数。
测试使用模拟数据库/服务，不代表实际 MySQL 写入成功。本环境没有 Docker 引擎，因此未执行容器构建，也没有访问你的 Aiven/GitHub 账户或完成公网部署。

## 官方参考

- [Aiven Runtime](https://aiven.io/docs/products/runtime)
- [Aiven Streamlit 模板目录](https://templates.aiven.io/)
- [Deploy application](https://aiven.io/docs/products/runtime/deploy-apps)
- [Containerfile / Dockerfile](https://aiven.io/docs/products/runtime/manifest-files/containerfiles)
- [Ports and public HTTPS](https://aiven.io/docs/products/runtime/ports)
- [Environment variables](https://aiven.io/docs/products/runtime/secrets-and-variables)
- [MySQL Workbench connection](https://aiven.io/docs/products/mysql/howto/connect-from-mysql-workbench)
- [Aiven CA certificates](https://aiven.io/docs/platform/concepts/tls-ssl-certificates)
- [MySQL Connector/Python SSL options](https://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html)
