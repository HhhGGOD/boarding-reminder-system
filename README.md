# 登机协同台

一个基于 FastAPI 的旅客催促登机系统。系统关联航班、旅客值机和旅客登机数据，查询“已值机但尚未登机”的旅客，并对催促操作进行审计留痕。

Oracle 只负责业务查询，催促审计仍保存在本地 SQLite，应用不会在 Oracle 中自动建表或写入演示数据。

> 当前默认开启演示模式：广播催促操作会写入催促记录表，但不会真正触发广播任务。

## 已实现

- 按航班日期、航班号查询航班
- 三表联查未登机旅客
- 旅客姓名、座位、类型、脱敏联系方式展示
- 单选、批量选择和批量催促
- 广播催促渠道占位
- 发送前再次核验旅客登机状态
- 五分钟重复催促冷却控制
- 催促记录与操作人审计
- SQLite 演示数据自动初始化
- OpenAPI 接口文档
- Docker 启动配置
- 基础 API 自动化测试

## 技术栈

- Python 3.11+
- FastAPI
- SQLAlchemy 2
- Jinja2
- 原生 HTML、CSS 和少量 JavaScript
- SQLite（演示），可替换为 PostgreSQL、MySQL、SQL Server 或 Oracle

## 本地运行

PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

浏览器打开：

- 页面：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/docs>

首次启动会自动生成 SQLite 数据库和当天的三个演示航班：

- MU5101
- CA1888
- CZ6502

## Docker 运行

```powershell
docker start oracle-free
docker start boarding-reminder
```
```
docker stop oracle-free
docker stop boarding-reminder
```


## 数据库配置

### Oracle demo2

在项目根目录创建不会提交到 Git 的 `.env.local`：

```text
APP_NAME=登机协同台
DATA_SOURCE=oracle
DATABASE_URL=sqlite:///./boarding_reminder_audit.sqlite3
DEMO_MODE=true
REMINDER_COOLDOWN_SECONDS=300
DEFAULT_OPERATOR=值机保障-Oracle联调
ORACLE_HOST=127.0.0.1
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=FREEPDB1
ORACLE_USER=DCS_SYS
ORACLE_PASSWORD=请填写本机密码
ORACLE_SCHEMA=DCS_SYS
ORACLE_CHECKED_IN_STATUSES=AC
ORACLE_BOARDED_STATUSES=BD
```

安装依赖并运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

健康检查：<http://127.0.0.1:8000/api/health>

当前联查口径：

```text
TA_FLIGHT.FLT_ID = TA_PSRBASICINFO.SEG_FLTID
TA_PSRBASICINFO.(SEG_FLTID, PSR_HOSTNBR)
    = TAB_PSRSTATUS.(PSRB_FLTID, PSRB_HOSTNBR)
PSR_STATUS = AC 表示纳入已值机旅客
不存在 PSRB_STATUS = BD 的记录表示尚未登机
```

复制 `.env.example` 为 `.env`，或在运行环境中设置变量：

```text
DATABASE_URL=sqlite:///./boarding_reminder.sqlite3
DEMO_MODE=true
REMINDER_COOLDOWN_SECONDS=300
DEFAULT_OPERATOR=值机保障-演示账号
```

连接 PostgreSQL 的示例：

```text
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
```

连接其他数据库时，需要在 `requirements.txt` 中增加对应 SQLAlchemy 驱动。

## 替换真实的三个表

需要重点修改：

1. `app/models.py`
   - 把 `Flight` 映射到真实航班表
   - 把 `PassengerCheckin` 映射到真实值机表
   - 把 `PassengerBoarding` 映射到真实登机表

2. `app/service.py`
   - `list_flights()`：航班查询和统计
   - `_unboarded_statement()`：未登机旅客联查

3. `app/seed.py`
   - 接入真实库后可以删除演示数据初始化，或通过环境变量关闭

当前查询口径是：

```text
航班处于有效状态
+ 值机状态为 CHECKED_IN
+ 没有状态为 BOARDED 的登机记录
= 未登机旅客
```

如果真实登机表是事件流水表，需要把 `_unboarded_statement()` 改为“先取每位旅客最新一条登机事件，再判断其状态”。

## 表关联要求

不建议仅通过航班号关联。正式数据最好具备：

```text
flight_instance_id = 航班日期 + 航班号 + 起降站 + 航段的唯一实例
passenger_id       = 当前航段内的旅客唯一标识
```

值机表和登机表都应使用 `flight_instance_id + passenger_id` 与航班、旅客关联。

## 接口

| 方法 | 地址 | 用途 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/flights?date=YYYY-MM-DD&flight_no=MU5101` | 查询航班 |
| GET | `/api/flights/{flight_id}/unboarded-passengers` | 查询未登机旅客 |
| POST | `/api/reminders` | 发起催促 |
| GET | `/api/flights/{flight_id}/reminders` | 查询催促记录 |

## 接入真实催促平台

当前 `app/service.py` 中的 `create_reminders()` 只写入模拟结果。正式接入时建议新增独立适配器，例如：

```text
app/integrations/broadcast.py
```

适配器应返回平台消息 ID 和发送状态，并写入 `boarding_reminder_log`。生产环境还建议增加：

- 单点登录或 AD 认证
- 查询权限与催促权限分离
- 消息队列和失败重试
- 操作审计导出
- 数据同步延迟提示
- 手机号和证件号脱敏
- 生产主库只读账号或只读副本

## 测试

```powershell
pytest -q
```
