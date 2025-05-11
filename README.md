# TG营销系统 - Python工作节点组件


## 功能实现（2025-05-11）

- **任务处理**: 处理各种Telegram操作，包括发送消息、加入/退出群组、添加联系人等
- **分布式架构**: 可以水平扩展以并行处理多个任务
- **RabbitMQ集成**: 通过消息队列与Golang后端通信
- **Telegram集成**: 使用Telethon与Telegram的API交互

## 目录结构

```
tg_manager_task/
├── config/               # 配置设置
│   └── settings.py       # 系统配置
├── telegram/             # Telegram操作
│   ├── client.py         # Telegram客户端封装
│   └── task_executor.py  # 任务执行逻辑
├── utils/                # 工具模块
│   ├── api_client.py     # 用于API通信的HTTP客户端
│   └── rabbitmq_client.py # RabbitMQ客户端
├── main.py               # 主入口点
└── requirements.txt      # Python依赖包
```

## 支持的任务类型

1. **send_message**: 向个人或群组发送消息
2. **join_group**: 加入Telegram群组或频道
3. **leave_group**: 退出Telegram群组或频道
4. **add_contact**: 添加联系人到地址簿
5. **check_account**: 检查账号状态/健康状况
6. **extract_members**: 从群组中提取成员

## 安装

1. 安装依赖包：
```bash
pip install -r requirements.txt
```

2. 配置环境变量或编辑 `config/settings.py`：
```bash
# 必需的Telegram API凭证
export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash

# RabbitMQ连接
export RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# API连接
export API_BASE_URL=http://localhost:8080/api/v1
```

3. 运行工作节点：
```bash
python main.py
```

## 工作节点注册流程

1. 工作节点在启动时注册到API
2. 它接收一个唯一的worker_id
3. 它开始向API发送心跳
4. 它开始从RabbitMQ消费任务
5. 任务结果通过RabbitMQ发送回API

## 与Golang后端集成

工作节点通过以下方式与Golang后端集成：

1. 使用RabbitMQ进行任务分发和结果报告
2. 使用REST API调用进行工作节点注册和心跳检测
3. 通过数据库中的任务记录共享任务状态

## 部署

工作节点可以使用Docker进行部署，便于扩展：

```bash
# 构建Docker镜像
docker build -t tg-worker .

# 运行容器
docker run -d --name tg-worker-1 \
  -e TELEGRAM_API_ID=your_api_id \
  -e TELEGRAM_API_HASH=your_api_hash \
  -e RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  -e API_BASE_URL=http://api:8080/api/v1 \
  tg-worker
```
