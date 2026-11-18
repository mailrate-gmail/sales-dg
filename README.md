# AI 会谈辅助系统

本项目是一个本地单机运行的 AI 会谈辅助系统原型。系统在客户笔记本电脑本地运行 `client` 和 `server`，通过浏览器录音，后端使用本地 `faster-whisper` 完成语音转文字，使用 `SpeechBrain` 进行声纹识别，并通过 OpenAI Compatible 大模型 API 生成会谈建议回复和会后总结。

![演示流程](docs/screenshots/demo-flow.svg)

## 1. 核心能力

- 本地 Web 前端页面；
- 本地 FastAPI 后端服务；
- 输入会晤目标；
- 维护参会人列表；
- 录入参会人声纹样本；
- 基于浏览器 WebAudio RMS 能量检测进行语音切分；
- 本地 faster-whisper 转写；
- 本地 SpeechBrain 声纹匹配；
- 手动修正消息说话人；
- 页面维护 LLM / Whisper / 声纹阈值 / 能量阈值配置；
- 根据参会人配置判断是否生成 AI 建议回复；
- 客户发言白色展示，我方发言黄色展示；
- 一键生成结构化会后总结；
- 会话记录和导出 Markdown 保存在本地文件中。

## 2. 技术栈

```text
前端：React + Vite + TypeScript
后端：Python + FastAPI
语音识别：faster-whisper
声纹识别：SpeechBrain
音频处理：ffmpeg
大模型：OpenAI Compatible API
部署：Docker Compose
CI：GitHub Actions
```

## 3. 快速启动

### 3.1 准备配置

项目可在没有 `.env` 的情况下启动，页面“模型配置”中也可以维护运行时配置。推荐先复制示例配置：

```bash
cp .env.example .env
```

编辑 `.env`，填入你的大模型 API Key：

```env
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的API_KEY
```

### 3.2 Docker Compose 启动

```bash
docker compose up --build
```

启动后访问：

```text
http://localhost:3000
```

后端接口地址：

```text
http://localhost:8000
```

API 文档：[`docs/API.md`](docs/API.md)

健康检查：

```bash
curl http://localhost:8000/api/health
```

## 4. 本地开发与验证

### 4.1 前端独立开发模式（推荐调试前端）

后端继续使用 Docker，前端在宿主机直接运行 Vite。这样修改 `client/src` 下的文件会自动热更新，不需要每次执行 `docker compose up -d --build`。

先启动后端服务：

```bash
docker compose up -d server
```

如果之前已经启动了 Docker 里的前端容器，先停止它，避免占用 3000 端口：

```bash
docker compose stop client
```

再启动本地前端开发服务：

```bash
cd client
npm install
npm run dev:host
```

访问：

```text
http://localhost:3000
```

前端会通过 Vite 代理把 `/api` 请求转发到后端 `http://localhost:8000`。

如果通过 SSH 访问远程开发机，只需要转发前端端口：

```bash
ssh -N -L 8099:localhost:3000 用户名@远程服务器地址
```

然后在本地浏览器访问：

```text
http://localhost:8099
```

### 4.2 构建与检查

前端构建：

```bash
cd client
npm install
npm run build
```

后端语法检查：

```bash
cd server
python -m compileall app
```

Docker 构建：

```bash
docker compose build
```

> 后端依赖使用 PyTorch CPU wheel，避免默认拉取大型 CUDA 运行时包。

## 5. 本地数据目录

运行后会在项目根目录生成 `data/`：

```text
data/
├── model_config.json
├── participants.json
├── participants/
├── sessions/
├── audio/
└── exports/
```

## 6. 演示流程

1. 打开 `http://localhost:3000`；
2. 在“模型配置”中检查 LLM、Whisper、声纹阈值、能量切分阈值；
3. 添加参会人，并设置角色：我方 / 客户 / 其他；
4. 为参会人录入 10 秒左右声纹样本；
5. 输入会晤目标并点击“新建会谈”；
6. 点击“开始录音”；
7. 前端按能量阈值和静音时长自动切分语音片段并上传；
8. 后端完成转写和声纹识别；
9. 如识别错误，在消息右侧下拉框手动修正说话人；
10. 对需要答复的参会人发言生成 AI 建议回复；
11. 会后点击“生成会后总结”；
12. 点击“导出会话”保存 Markdown 文件。

## 7. 许可证

本项目使用 [MIT License](LICENSE)。
