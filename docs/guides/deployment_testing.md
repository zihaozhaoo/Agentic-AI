# AgentBeats v2 部署与测试指南

本文档补充了基础的环境配置指南，专门针对 AgentBeats v2 在 v2.agentbeats.org 平台上的部署和测试流程。

---

## **前置条件**

在开始之前，请确保已完成以下步骤（参见主操作指南）：

- ✅ 已下载并解压代码库
- ✅ 已运行 `uv sync` 并激活虚拟环境
- ✅ 已安装并配置 ngrok
- ✅ 已创建两个 ngrok 域名：
  - `green.agentic-ai-taxi-routing.ngrok.com.ngrok.app`
  - `white.agentic-ai-taxi-routing.ngrok.com.ngrok.app`

---

## **重要修复说明**

### **问题背景**

在使用 `agentbeats run_ctrl` 模式时，controller 会为 agent 设置 `AGENT_URL` 环境变量，指向完整的代理路径：
```
https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app/to_agent/<agent_id>
```

但原始代码中，agent 会优先使用 `CLOUDRUN_HOST` + `default_path`，导致 agent card 中的 URL 变成：
```
https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app/green
```

这会导致 404 错误。

### **已修复内容**

已修改以下文件，使其优先使用 controller 提供的 `AGENT_URL`：

1. `agentbeats_v2/src/green_agent/agent.py`
2. `agentbeats_v2_white/src/white_agent/agent.py`

在 `_resolve_networking()` 函数中添加了 `AGENT_URL` 的优先级检查：

```python
def _resolve_networking(default_host: str, default_port: int, default_path: str = ""):
    """Resolve bind address and public URL based on env vars for cloud/public runs."""
    host = os.environ.get("AGENT_HOST", default_host)
    port = int(os.environ.get("AGENT_PORT", default_port))
    https_enabled = os.environ.get("HTTPS_ENABLED", "").lower() in ("1", "true", "yes")
    scheme = "https" if https_enabled else "http"

    # Priority 1: AGENT_URL set by controller (for agentbeats run_ctrl mode)
    agent_url = os.environ.get("AGENT_URL")
    if agent_url:
        return host, port, agent_url

    # Priority 2: PUBLIC_URL explicitly set by user
    public_url = os.environ.get("PUBLIC_URL")
    if public_url:
        return host, port, public_url

    # Priority 3: Construct from CLOUDRUN_HOST + CLOUDRUN_PATH
    cloudrun_host = os.environ.get("CLOUDRUN_HOST")
    path = os.environ.get("CLOUDRUN_PATH", default_path or "")
    if path and not path.startswith("/"):
        path = "/" + path
    if cloudrun_host:
        cloudrun_host = cloudrun_host.rstrip("/")
        return host, port, f"{scheme}://{cloudrun_host}{path}"

    # Priority 4: Default to localhost
    return host, port, f"{scheme}://{host}:{port}"
```

---

## **1. 启动 ngrok 隧道**

### **1.1 启动 Green Agent 隧道**

在终端 1 中运行：

```bash
ngrok http 8010 --url=green.agentic-ai-taxi-routing.ngrok.com.ngrok.app
```

### **1.2 启动 White Agent 隧道**

在终端 2 中运行：

```bash
ngrok http 8011 --url=white.agentic-ai-taxi-routing.ngrok.com.ngrok.app
```

**注意事项：**
- 保持这两个终端窗口运行，不要关闭
- 确认看到 "Session Status: online" 状态
- 记录下 "Forwarding" 行显示的 URL

---

## **2. 启动 Agent Controllers**

**关键要点：Green 和 White controllers 必须在不同的目录下运行！**

### **2.1 启动 Green Agent Controller**

在终端 3 中运行：

```bash
# 确保在正确的目录
cd /Users/zhaozihao/Desktop/Agentic-AI/agentbeats_v2

# 启动 controller
HTTPS_ENABLED=true \
PORT=8010 \
CLOUDRUN_HOST=green.agentic-ai-taxi-routing.ngrok.com.ngrok.app \
ROLE=green \
agentbeats run_ctrl
```

### **2.2 启动 White Agent Controller**

在终端 4 中运行：

```bash
# 注意：这里进入的是 agentbeats_v2_white 目录
cd /Users/zhaozihao/Desktop/Agentic-AI/agentbeats_v2_white

# 启动 controller
HTTPS_ENABLED=true \
PORT=8011 \
CLOUDRUN_HOST=white.agentic-ai-taxi-routing.ngrok.com.ngrok.app \
ROLE=white \
agentbeats run_ctrl
```

### **2.3 验证启动成功**

在两个 controller 的终端中，应该看到类似输出：

```
Found existing .ab/agents file from previous runs, cleaning up...
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8010 (Press CTRL+C to quit)
```

---

## **3. 测试 Agent 状态**

### **3.1 获取当前 Agent IDs**

```bash
# Green agent
curl http://localhost:8010/agents | python3 -m json.tool

# White agent
curl http://localhost:8011/agents | python3 -m json.tool
```

**期望输出示例：**

```json
{
    "0569216d3257479da2a4549a2ac0fa38": {
        "url": "https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app/to_agent/0569216d3257479da2a4549a2ac0fa38",
        "internal_port": 47102,
        "state": "running"
    }
}
```

**检查点：**
- ✅ Green 和 White 应该显示**不同的 agent IDs**
- ✅ 两个 agent 的 `state` 都应该是 `"running"`
- ✅ URLs 应该包含完整的 `/to_agent/<id>` 路径

### **3.2 验证 Agent Card URLs**

从上一步获取 agent IDs（用实际 ID 替换 `<green_id>` 和 `<white_id>`）：

```bash
# 检查 Green agent card
curl -s http://localhost:8010/to_agent/<green_id>/.well-known/agent-card.json | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Green Agent URL: {d[\"url\"]}')"

# 检查 White agent card
curl -s http://localhost:8011/to_agent/<white_id>/.well-known/agent-card.json | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f'White Agent URL: {d[\"url\"]}')"
```

**期望输出：**

```
Green Agent URL: https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app/to_agent/<green_id>
White Agent URL: https://white.agentic-ai-taxi-routing.ngrok.com.ngrok.app/to_agent/<white_id>
```

**⚠️ 重要检查：**
- URL 必须是 `/to_agent/<id>` 格式
- **不能**是 `/green` 或 `/white`
- 如果是错误格式，说明修复未生效，需要重启 controllers

### **3.3 测试外部可访问性**

```bash
# 测试 Green agent 通过 ngrok 访问
curl -s https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app/agents | python3 -m json.tool

# 测试 White agent 通过 ngrok 访问
curl -s https://white.agentic-ai-taxi-routing.ngrok.com.ngrok.app/agents | python3 -m json.tool
```

**检查点：**
- ✅ 应该返回与本地测试相同的 agent 信息
- ✅ HTTP 状态码应该是 200
- ✅ 没有 ngrok 错误页面

### **3.4 验证 Agent Cards 可通过 ngrok 访问**

```bash
# 测试 Green agent card（替换 <green_id>）
curl -s https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app/to_agent/<green_id>/.well-known/agent-card.json | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✅ Green agent accessible\nName: {d[\"name\"]}\nURL: {d[\"url\"]}')"

# 测试 White agent card（替换 <white_id>）
curl -s https://white.agentic-ai-taxi-routing.ngrok.com.ngrok.app/to_agent/<white_id>/.well-known/agent-card.json | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✅ White agent accessible\nName: {d[\"name\"]}\nURL: {d[\"url\"]}')"
```

---

## **4. 在 v2.agentbeats.org 注册 Agents**

### **4.1 访问平台**

打开浏览器访问：https://v2.agentbeats.org

使用 GitHub 账号登录。

### **4.2 注册 Green Agent**

1. 点击 "Add Agent" 或 "Register Agent"
2. 填写表单：
   - **Name**: `greenagent`（或你喜欢的名字）
   - **Deploy Type**: `Remote`
   - **Is Assessor (Green) Agent**: ✅ 勾选
   - **Controller URL**: `https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app`
     - ⚠️ **只填基础 URL，不要包含** `/to_agent/<id>`
   - **Git URL** (可选): 留空或填写你的代码仓库
   - **Git Branch** (可选): `main`

3. 点击 "Create Agent"

### **4.3 注册 White Agent**

1. 再次点击 "Add Agent"
2. 填写表单：
   - **Name**: `whiteagent`
   - **Deploy Type**: `Remote`
   - **Is Assessor (Green) Agent**: ❌ 不勾选
   - **Controller URL**: `https://white.agentic-ai-taxi-routing.ngrok.com.ngrok.app`
   - **Git URL/Branch**: 可选

3. 点击 "Create Agent"

### **4.4 验证 Agent 注册**

平台会自动验证 agents：
- 调用 `/agents` 端点获取 agent IDs
- 检查 agent card 的可访问性
- 验证协议版本兼容性

如果注册成功，你应该能在 agents 列表中看到你的 agents。

---

## **5. 创建和运行 Assessment**

### **5.1 创建 Assessment**

1. 在平台上点击 "Create Assessment"
2. 选择你注册的 Green Agent
3. 选择你注册的 White Agent（如果需要）
4. 选择配置（`default`）
5. 点击 "Create Assessment"

### **5.2 启动 Assessment**

Assessment 创建后会进入 `PENDING` 状态。

**正常流程：**
1. PENDING（等待资源分配）→ 1-3 分钟
2. RUNNING（执行中）→ 根据任务大小
3. COMPLETED（完成）

### **5.3 监控 Assessment 执行**

在你的 terminal 中（运行 controllers 的窗口），你应该能看到来自平台的请求：

```
INFO:     34.53.40.129:0 - "GET /agents/<agent_id> HTTP/1.1" 200 OK
INFO:     34.53.40.129:0 - "POST /to_agent/<agent_id>/messages HTTP/1.1" 200 OK
```

**关键 IP 地址：**
- `34.53.40.129` - v2.agentbeats.org 平台服务器
- 如果看到这个 IP 的请求，说明 assessment 已经开始执行

### **5.4 查看 Assessment 结果**

Assessment 完成后：
1. 在平台上点击 assessment 查看详情
2. 查看 logs、metrics 和结果
3. 本地也会生成可视化文件：
   - `logs/visualizations/`

---

## **6. 常见问题排查**

### **6.1 问题：Agent Card URL 显示 `/green` 而不是 `/to_agent/<id>`**

**原因：** 代码修复未生效

**解决方案：**
1. 确认已修改 `agent.py` 文件中的 `_resolve_networking()` 函数
2. 重启 controllers（Ctrl+C 停止，然后重新运行启动命令）
3. 重新验证 agent card URL

### **6.2 问题：两个 controllers 显示相同的 agent ID**

**原因：** 两个 controllers 在同一个目录下运行，共享了 `.ab/agents` 文件夹

**解决方案：**
1. 停止所有 controllers
2. 确认 Green controller 在 `agentbeats_v2/` 目录运行
3. 确认 White controller 在 `agentbeats_v2_white/` 目录运行
4. 重新启动

**验证方法：**
```bash
# 检查进程的工作目录
ps aux | grep "agentbeats run_ctrl"
lsof -p <pid> | grep cwd
```

### **6.3 问题：Platform 无法访问 agents (404 错误)**

**可能原因：**

1. **ngrok 隧道未运行**
   ```bash
   # 检查 ngrok 进程
   ps aux | grep ngrok
   ```

2. **Controllers 未运行**
   ```bash
   curl http://localhost:8010/agents
   curl http://localhost:8011/agents
   ```

3. **注册的 controller URL 错误**
   - 应该是基础 URL，不包含路径
   - ✅ 正确：`https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app`
   - ❌ 错误：`https://green.agentic-ai-taxi-routing.ngrok.com.ngrok.app/to_agent/<id>`

### **6.4 问题：Assessment 一直 PENDING**

**排查步骤：**

1. **刷新页面** - 状态可能已更新但页面未刷新

2. **检查 terminal 日志** - 看是否收到来自 `34.53.40.129` 的请求
   ```bash
   tail -f agentbeats_v2/.ab/agents/*/stdout.log
   ```

3. **等待 2-3 分钟** - 平台可能在处理队列

4. **重启 Assessment** - 点击 "Restart Assessment" 按钮

5. **验证 agents 状态**
   ```bash
   curl http://localhost:8010/agents
   curl http://localhost:8011/agents
   ```

### **6.5 问题：收到大量旧 agent ID 的 404 错误**

**原因：** 平台的旧 assessments 还在尝试访问之前的 agent IDs

**解决方案：**
1. 这些 404 是预期行为，可以忽略
2. 在平台上删除旧的 assessments
3. 使用新注册的 agents 创建新的 assessment
4. 新 assessment 会使用正确的 agent IDs

**判断方法：**
- 如果请求的 agent ID 不在当前的 `/agents` 列表中，就是旧 ID
- 检查当前 IDs：
  ```bash
  curl http://localhost:8010/agents | python3 -c "import sys, json; print(list(json.load(sys.stdin).keys()))"
  ```

---

## **7. 完整测试检查清单**

使用此清单确保所有配置正确：

### **环境准备**
- [ ] 代码已下载并解压
- [ ] `uv sync` 已运行
- [ ] 虚拟环境已激活
- [ ] ngrok 已安装并配置 token

### **代码修复**
- [ ] `agentbeats_v2/src/green_agent/agent.py` 已修改
- [ ] `agentbeats_v2_white/src/white_agent/agent.py` 已修改
- [ ] `_resolve_networking()` 优先检查 `AGENT_URL`

### **服务启动**
- [ ] Green ngrok 隧道运行中（端口 8010）
- [ ] White ngrok 隧道运行中（端口 8011）
- [ ] Green controller 在 `agentbeats_v2/` 目录运行
- [ ] White controller 在 `agentbeats_v2_white/` 目录运行

### **本地测试**
- [ ] `curl localhost:8010/agents` 返回 Green agent
- [ ] `curl localhost:8011/agents` 返回 White agent
- [ ] 两个 agents 有不同的 IDs
- [ ] 两个 agents 状态都是 "running"
- [ ] Agent card URLs 格式正确（`/to_agent/<id>`）

### **外部访问测试**
- [ ] 通过 ngrok URL 可以访问 `/agents` 端点
- [ ] 通过 ngrok URL 可以访问 agent cards
- [ ] Agent card 中的 URL 字段正确

### **平台注册**
- [ ] Green agent 已在平台注册
- [ ] White agent 已在平台注册
- [ ] Controller URLs 填写正确（不含路径）
- [ ] Agents 通过平台验证

### **Assessment 运行**
- [ ] 创建新的 assessment
- [ ] Assessment 状态变为 RUNNING
- [ ] Terminal 中看到平台服务器请求
- [ ] Assessment 成功完成

---

## **8. 快速启动脚本（可选）**

为了简化启动流程，可以创建启动脚本。

### **8.1 创建 Green Agent 启动脚本**

创建文件 `agentbeats_v2/start_green.sh`：

```bash
#!/bin/bash
set -e

echo "Starting Green Agent Controller..."
cd "$(dirname "$0")"

HTTPS_ENABLED=true \
PORT=8010 \
CLOUDRUN_HOST=green.agentic-ai-taxi-routing.ngrok.com.ngrok.app \
ROLE=green \
agentbeats run_ctrl
```

### **8.2 创建 White Agent 启动脚本**

创建文件 `agentbeats_v2_white/start_white.sh`：

```bash
#!/bin/bash
set -e

echo "Starting White Agent Controller..."
cd "$(dirname "$0")"

HTTPS_ENABLED=true \
PORT=8011 \
CLOUDRUN_HOST=white.agentic-ai-taxi-routing.ngrok.com.ngrok.app \
ROLE=white \
agentbeats run_ctrl
```

### **8.3 使用脚本**

```bash
# 添加执行权限
chmod +x agentbeats_v2/start_green.sh
chmod +x agentbeats_v2_white/start_white.sh

# 在不同终端运行
./agentbeats_v2/start_green.sh
./agentbeats_v2_white/start_white.sh
```

---

## **9. 相关资源**

### **文档**
- AgentBeats v2 README: `agentbeats_v2/README.md`
- A2A Protocol: https://a2a-spec.org/

### **Platform**
- v2.agentbeats.org: https://v2.agentbeats.org
- Platform 文档: https://docs.agentbeats.org

### **工具**
- ngrok 文档: https://ngrok.com/docs
- uvicorn 文档: https://www.uvicorn.org/

---

## **10. 总结**

**关键要点：**

1. **代码修复很重要** - 确保 `AGENT_URL` 优先级最高
2. **目录分离** - Green 和 White controllers 必须在不同目录运行
3. **URL 格式** - Agent card 的 URL 必须是 `/to_agent/<id>` 格式
4. **注册 URL** - 在平台注册时只填基础 controller URL
5. **监控日志** - 通过 terminal 日志监控 assessment 执行状态

遵循本指南，你应该能够成功部署和测试 AgentBeats v2 agents！
