环境要求:

```bash
python3 --version  # Should be 3.11.14
node -v            # Should be v24.8.0
npm -v             # Should be 11.6.0
```

Build Agentbeats

```bash
cd agentbeats
pip install -U pip
pip install -e .
```

Verify the installation:

```bash
agentbeats --help
agentbeats check
```

设置 API KEY

```bash
export OPENAI_API_KEY="sk-your-openai-api-key-here"
export OPENROUTER_API_KEY="sk-your-openai-api-key-here"
```

安装前端依赖：

```bash
agentbeats install_frontend
agentbeats install_frontend --webapp_version webapp-v2
```

这个时候如果用

```bash
agentbeats check
```

检查，有可能依然提示前端未安装，不用管他。

部署 agentbeats 平台（检查端口 5173，9000，9001 是否开放）：

```bash
agentbeats deploy --deploy_mode dev
```

如果能正常运行（没有退出），应该环境就没问题了，后面可以直接让 Cursor 开始写

---

## 运行 Agentic-AI Agent (RegexBaselineAgent)

以下步骤说明如何在 AgentBeats 平台上运行我们自定义的 `RegexBaselineAgent`。

### 1. 设置虚拟环境 (Virtual Environment)

为了避免依赖冲突，建议创建一个 Python 3.11+ 的虚拟环境。

**步骤:**

1.  **创建虚拟环境** (在 `Agentic-AI` 根目录下):

    ```bash
    # 确保你有 Python 3.11+
    python3 -m venv .venv
    ```

2.  **激活虚拟环境**:

    ```bash
    source .venv/bin/activate
    ```

    _(注意: 每次打开新终端都需要执行此命令)_

3.  **安装依赖**:
    ```bash
    # 安装 agentbeats (开发模式), uvicorn (服务器), 和 openai-agents
    pip install -e ../agentbeats uvicorn openai-agents
    ```

### 2. 启动 Agent

确保你已经在虚拟环境中 (`source .venv/bin/activate`)。

运行适配器脚本:

```bash
python agentbeats_adapter.py
```

Agent 将在 `http://0.0.0.0:8001` 启动。

### 3. 验证 Agent 状态

在另一个终端中 (不需要虚拟环境):

```bash
curl http://localhost:8001/.well-known/agent.json
```

你应该能看到返回的 JSON 数据，包含 Agent 的描述和技能。

### 4. 注册到 AgentBeats 平台

确保 AgentBeats 平台正在运行 (在 `agentbeats` 目录下运行 `agentbeats deploy --deploy_mode dev`)。

然后运行以下命令注册 Agent:

```bash
curl -X POST http://localhost:9000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "alias": "Regex Baseline Agent",
    "agent_url": "http://localhost:8001",
    "launcher_url": "http://localhost:8001",
    "is_green": false
  }'
```

注册成功后，你可以在 AgentBeats 的 Web UI (`http://localhost:5173`) 中看到该 Agent。
