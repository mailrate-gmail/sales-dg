# Roadmap

本文档记录后续优化方向与待评估事项。

## 性能与服务端技术栈

### 1. 评估使用 Go 重写/拆分 Server 以提升系统响应速度

当前 server 使用 Python + FastAPI 实现，开发效率高、生态完善，适合快速迭代 ASR、声纹、Agent 记忆与 LLM 调用逻辑。

后续可评估将部分或全部 server 能力迁移到 Go，目标是提升系统响应速度与并发处理能力，尤其是：

- WebSocket 音频流接入与消息分发；
- 高频实时事件处理；
- 多会议并发时的连接管理；
- 本地规则分析、上下文更新等轻量但高频逻辑；
- 服务启动速度、内存占用与部署体积。

需要注意：当前主要耗时仍可能来自 ASR 推理、声纹识别和远程 LLM 网络调用。是否使用 Go 应以 profiling 结果为依据，优先确认 Python server 本身是否已成为瓶颈。

可选落地路径：

1. 保持 Python 主服务不变，仅用 Go 拆分高频 WebSocket 网关；
2. 将本地会话分析与上下文管理抽成 Go 微服务；
3. 在性能瓶颈明确后，再评估完整迁移 server。

## ASR 服务选型与网络延迟

### 1. Oracle OCI Speech 测试记录

曾经测试过 Oracle OCI Speech，结论如下：

1. OCI Speech 的 Whisper 模型支持中文，但中文识别率太差，几乎不能满足实际使用；
2. 网络延时也满足不了实际业务需求，不适合作为当前本地实时会谈辅助系统的主实时 ASR 路径。

当前建议：

- 实时识别主路径继续优先使用本地 FunASR streaming；
- faster-whisper 保留为本地短音频 fallback；
- Oracle OCI Speech 暂作为云端 ASR 预留选项，不作为默认实时路径。
