# OPC Platform 部署指南

> 支持：本地部署 · 阿里云 · 腾讯云 · 华为云 · 自建服务器

---

## 架构概览

```
                            ┌─────────────┐
                      80/443│   Nginx     │ 反向代理 + SSL
                  ┌─────────┤  (总入口)   ├─────────┐
                  │         └─────────────┘         │
                  │                                 │
            /api/*│                                 │/*
                  ▼                                 ▼
          ┌──────────────┐                 ┌──────────────┐
          │   FastAPI    │                 │   Web 前端    │
          │   :8000      │                 │   Nginx :80   │
          └──────┬───────┘                 └──────────────┘
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
   ┌────────┐┌──────┐┌────────┐
   │Postgres││Redis ││Celery  │
   │+pgvect ││      ││Worker  │
   └────────┘└──────┘│+Beat   │
                     └────────┘
```

---

## 一、本地部署（Docker 一键启动）

### 前提
- Docker + Docker Compose 已安装
- 2GB+ 可用内存

### 步骤

```bash
# 1. 克隆项目
git clone https://github.com/tonyscount/OPC-operating.git
cd OPC-operating

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env：至少填 OPENAI_API_KEY（LLM 调用需要）

# 3. 一键启动
docker compose up -d

# 4. 查看状态
docker compose ps

# 5. 访问
# Web 前端: http://localhost:3000
# API 文档: http://localhost:8000/docs

# 6. 停止
docker compose down
```

### 开发模式（只启动基础设施，API 本地跑）

```bash
# 启动 PG + Redis
docker compose -f docker-compose.dev.yml up -d

# 本地跑 API（方便 debug）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 本地跑前端
cd web
npm install --registry=https://registry.npmmirror.com
npm run dev
```

---

## 二、阿里云 ECS 部署

### 1. 准备 ECS
- 配置：2C4G 起步，推荐 4C8G
- 系统：Ubuntu 22.04 / CentOS 7.9
- 安全组：开放 80/443/22 端口
- 域名：A 记录指向 ECS 公网 IP

### 2. 安装 Docker

```bash
# Ubuntu
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update && sudo apt install -y docker-ce docker-compose-plugin

# 配置国内镜像加速
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["https://registry.cn-hangzhou.aliyuncs.com"]
}
EOF
sudo systemctl restart docker
```

### 3. 部署

```bash
git clone https://github.com/tonyscount/OPC-operating.git
cd OPC-operating
cp .env.example .env
# 编辑 .env: 填 API Key、JWT 密钥、DB 密码

# 启动
docker compose up -d

# 查看日志确认启动
docker compose logs -f api
```

### 4. 配置 SSL 证书（阿里云免费证书）

```bash
# 在阿里云 SSL 证书控制台申请免费证书 → 下载 Nginx 格式
# 上传到服务器
mkdir -p nginx/certs
# 将 .pem 和 .key 文件放到 nginx/certs/
# 重命名为 fullchain.pem 和 privkey.pem
# 重启 nginx
docker compose restart nginx
```

### 5. 数据备份（阿里云 OSS）

```bash
# 定时备份脚本 (crontab -e, 每天凌晨 3 点)
0 3 * * * cd /opt/OPC-operating && \
  docker compose exec -T postgres pg_dump -U opc_user opc_platform | \
  gzip > backup_$(date +\%Y\%m\%d).sql.gz && \
  ossutil cp backup_*.sql.gz oss://opc-backups/ && \
  find backup_*.sql.gz -mtime +7 -delete
```

---

## 三、腾讯云 Lighthouse / CVM 部署

### 1. 准备
- Lighthouse 4C8G 或 CVM 同等配置
- 系统：Ubuntu 22.04
- 防火墙：开放 80/443/22

### 2. 安装 Docker（腾讯云镜像源）

```bash
curl -fsSL https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update && sudo apt install -y docker-ce docker-compose-plugin

# 镜像加速
sudo tee /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
EOF
sudo systemctl restart docker
```

### 3. 部署步骤（同上）

```bash
git clone https://github.com/tonyscount/OPC-operating.git
cd OPC-operating
cp .env.example .env
# 编辑 .env
docker compose up -d
```

### 4. SSL 证书

```bash
# 方式一: 腾讯云 SSL 控制台申请免费证书 → 下载上传
# 方式二: 使用 acme.sh 自动申请 Let's Encrypt
curl https://get.acme.sh | sh
~/.acme.sh/acme.sh --issue -d your-domain.com -w /usr/share/nginx/html
~/.acme.sh/acme.sh --install-cert -d your-domain.com \
  --key-file nginx/certs/privkey.pem \
  --fullchain-file nginx/certs/fullchain.pem
docker compose restart nginx
```

### 5. 备份（腾讯云 COS）

```bash
# 使用 coscli 或 coscmd 上传到 COS
pip install coscmd
coscmd config -a SecretId -s SecretKey -b opc-backups-1234567890 -r ap-guangzhou
# crontab 定时备份同上
```

---

## 四、华为云 ECS 部署

### 1. 安装 Docker

```bash
# 华为云镜像源
sudo sed -i "s@http://.*archive.ubuntu.com@http://repo.huaweicloud.com@g" /etc/apt/sources.list
sudo apt update && sudo apt install -y docker.io docker-compose-v2

# 镜像加速
sudo tee /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["https://mirror.swr.myhuaweicloud.com"]
}
EOF
sudo systemctl restart docker
```

### 2. 部署（同上）

```bash
git clone https://github.com/tonyscount/OPC-operating.git
cd OPC-operating
cp .env.example .env
docker compose up -d
```

### 3. 备份（华为云 OBS）

```bash
# 使用 obsutil 上传
wget https://obs-community.obs.cn-north-1.myhuaweicloud.com/obsutil/current/obsutil_linux_amd64.tar.gz
tar -xzf obsutil_linux_amd64.tar.gz
./obsutil config -i=AK -k=SK -e=obs.cn-north-4.myhuaweicloud.com
```

---

## 五、自建服务器 / IDC 托管

适用于有自己的物理服务器或 IDC 托管机房的场景。

### 网络要求
- 公网 IP 或内网穿透（frp/ngrok）
- 如无公网 IP，可使用 Cloudflare Tunnel 免费方案

### 部署步骤

```bash
# 与阿里云步骤一致，镜像源使用 Docker Hub 或自建 registry
git clone https://github.com/tonyscount/OPC-operating.git
cd OPC-operating
cp .env.example .env
docker compose up -d
```

---

## 六、运维手册

### 日常命令

```bash
# 查看所有服务状态
docker compose ps

# 查看日志
docker compose logs -f --tail=100 api        # API 日志
docker compose logs -f --tail=100 worker     # Worker 日志
docker compose logs -f --tail=100 nginx      # Nginx 日志

# 重启单个服务
docker compose restart api
docker compose restart worker

# 更新部署
git pull
docker compose build api worker
docker compose up -d

# 数据库备份
docker compose exec postgres pg_dump -U opc_user opc_platform | gzip > backup_$(date +%Y%m%d_%H%M).sql.gz

# 数据库恢复
gunzip -c backup_20260711_0300.sql.gz | docker compose exec -T postgres psql -U opc_user opc_platform
```

### 监控建议

| 层级 | 工具 | 说明 |
|------|------|------|
| 服务器 | 阿里云云监控 / 腾讯云监控 | CPU/内存/磁盘/网络 |
| 容器 | `docker stats` / cAdvisor | 容器资源使用 |
| 日志 | `docker compose logs` / ELK | 集中日志管理 |
| 数据库 | pg_stat_statements / 慢查询日志 | 数据库性能 |
| 告警 | 企业微信/钉钉/飞书 Webhook | 异常通知 |

### 性能优化

```bash
# PostgreSQL 调优 (postgresql.conf)
shared_buffers = 256MB          # 25% 系统内存
effective_cache_size = 1GB      # 75% 系统内存
max_connections = 100

# Nginx 限流 (nginx.conf)
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req zone=api burst=50 nodelay;
```

### 安全 Checklist

- [ ] 修改默认 JWT_SECRET_KEY（生成随机 64 位字符串）
- [ ] 修改 PostgreSQL 默认密码
- [ ] 配置 SSL 证书
- [ ] 安全组仅开放必要端口（80/443/22）
- [ ] 配置数据库定期备份
- [ ] 设置日志轮转（防止磁盘写满）
- [ ] 配置防火墙（ufw / iptables）
- [ ] 定期更新 Docker 镜像

---

## 七、成本估算

| 方案 | 配置 | 月费（约） | 适用 |
|------|------|-----------|------|
| 阿里云 ECS | 2C4G | ¥200-300 | 小型团队/测试 |
| 阿里云 ECS | 4C8G | ¥400-600 | 中型团队/生产 |
| 腾讯云 Lighthouse | 4C8G | ¥120-200 | 高性价比 |
| 华为云 ECS | 4C8G | ¥400-600 | 政企客户 |
| 自建服务器 | 任意 | 电费+带宽 | 有自有硬件 |
| 本地部署 | 自己电脑 | 0 | 开发/测试 |
