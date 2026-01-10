#后端构建阶段
FROM python:3.11-slim as backend-builder

WORKDIR /app

# 安装系统依赖 (为了编译某些 python 包)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 使用国内源加速，生产环境可去掉
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 前端构建阶段
FROM node:18-alpine as frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm config set registry https://registry.npmmirror.com
RUN npm install
COPY frontend/ .
RUN npm run build

# 最终运行镜像
FROM python:3.11-slim

WORKDIR /app

# 安装运行时必要的系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 环境
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# 复制后端代码
COPY . .

# 复制前端构建产物到 Nginx 目录或后端静态目录 (这里假设用 FastAPI 托管静态文件作为简单方案)
# 生产环境建议用 Nginx 托管前端，这里为了单容器部署方便，我们复用 FastAPI
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 环境变量默认值
ENV PORT=8001
ENV HOST=0.0.0.0

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
