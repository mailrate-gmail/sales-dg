# AI 会谈辅助系统

本项目是一个本地单机运行的 AI 会谈辅助系统原型。

系统在客户笔记本电脑本地运行 `client` 和 `server`，通过浏览器录音，后端使用本地 `faster-whisper` 完成语音转文字，使用 `SpeechBrain` 进行声纹识别，并通过第三方大模型 API 生成会谈建议回复。

## 1. 核心能力

- 本地 Web 前端页面；
- 本地 FastAPI 后端服务；
- 输入会晤目标；
- 维护参会人列表；
- 录入参会人声纹样本；
- 浏览器录音并上传音频片段；
- 本地 faster-whisper 转写；
- 本地 SpeechBrain 声纹匹配；
- 根据参会人配置判断是否生成 AI 建议回复；
- 客户发言白色展示；
- 我方发言黄色展示；
- 会话记录保存在本地文件中。

## 2. 技术栈

```text
前端：React + Vite + TypeScript
后端：Python + FastAPI
语音识别：faster-whisper
声纹识别：SpeechBrain
音频处理：ffmpeg
大模型：第三方 OpenAI Compatible API
部署：Docker Compose
```

## 3. 快速启动

### 3.1 准备配置

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

## 4. 本地数据目录

运行后会在项目根目录生成 `data/`：

```text
data/
├── participants.json
├── participants/
├── sessions/
├── audio/
└── exports/
```

## 5. 使用流程

1. 打开页面；
2. 添加参会人；
3. 为参会人录入声纹样本；
4. 设置参会人角色：我方 / 客户 / 其他；
5. 设置该参会人是否需要 AI 答复；
6. 输入会晤目标；
7. 点击“开始录音”；
8. 系统按音频片段转写文字并识别说话人；
9. 如果该说话人需要 AI 答复，系统生成建议回复；
10. 点击“导出会话”保存 Markdown 文件。

## 6. 当前版本说明

这是第一版 MVP 骨架，重点验证完整链路。

当前版本为了简化实现，前端按固定时间片上传音频，后端对每个音频片段执行转写和声纹匹配。后续可以继续优化为更精细的能量检测切分、WebSocket 实时传输和更准确的 VAD。
