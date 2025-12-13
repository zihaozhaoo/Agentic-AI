# 🧪 Green Agent Evaluation Guide

本文档详细说明了如何使用 Green Agent 框架对 White Agent（调度算法）进行测试与评估。

---

## 📋 评估体系概览

我们的评估体系主要关注两个核心维度：

1.  **自然语言解析 (Parsing Accuracy)**
    *   能否准确识别起点 (Origin) 和终点 (Destination)？
    *   能否提取时间约束 (Time Constraints)？
    *   能否识别特殊需求 (如轮椅、多人乘车)？

2.  **调度效率 (Routing Efficiency)**
    *   **Revenue per Mile**: 每英里营收（越高越好）。
    *   **Deadhead Ratio**: 空驶率（越低越好）。
    *   **Response Time**: 乘客等待时间。

---

## 🤖 Baseline Agents (基准参照)

在开发你自己的 Agent 之前，请先运行 Baseline Agents 以建立性能参照坐标：

| Agent | 类型 | 预期表现 | 用途 |
| :--- | :--- | :--- | :--- |
| **DummyWhiteAgent** | Cheating | **Score: ~60**<br>Parsing: 100% | **仅用于调试**。它直接读取答案，代表了当前路由算法的理论上限。 |
| **RegexBaselineAgent** | Rule-based | **Score: ~15**<br>Parsing: ~40% | **合格线**。基于关键词匹配。你的 Agent 必须击败它。 |
| **RandomBaselineAgent** | Random | **Score: ~5**<br>Parsing: 0% | **下界**。代表完全随机的表现。 |

---

## 🚀 如何运行测试

### 1. 准备数据
确保项目根目录下存在以下文件：
*   `taxi_zone_lookup.csv` (出租车区域定义)
*   `fhvhv_tripdata_2025-01.parquet` (真实行程数据)

### 2. 快速冒烟测试 (Smoke Test)
如果你只想验证 Agent 是否能跑通，不关心具体分数：

```bash
python3 src/demo_baselines.py
```
*   **输入**: 一条固定的测试语句。
*   **输出**: 打印每个 Agent 的解析结果。

### 3. 完整评估 (Full Evaluation)
使用真实数据进行批量测试（默认 50 条请求）：

```bash
python3 examples/evaluate_baselines.py
```

**输出示例**:
```text
================================================================================
FINAL COMPARISON
================================================================================
Agent Name           | Score    | Origin Acc   | Dest Acc     | Rev/Mile  
----------------------------------------------------------------------
DummyAgent (Test)    | 59.62    | 100.0      % | 100.0      % | $3.20     
RegexBaseline        | 18.02    | 40.0       % | 42.0       % | $140.20   
RandomBaseline       | 4.58     | 0.0        % | 0.0        % | $0.60     
----------------------------------------------------------------------
```

---

## 📊 结果解读

### Score (综合得分)
*   范围：0 - 100
*   计算公式：`0.3 * Parsing_Score + 0.7 * Routing_Score`
*   **目标**: 你的 Agent 应该争取超过 **20分** (击败 RegexBaseline)。

### Origin/Dest Accuracy (解析准确率)
*   **RegexBaseline** 通常在 40% 左右，因为它无法理解 "Home", "Work" 或具体的 POI 名称（如 "Empire State Building"）。
*   如果你的 Agent 使用了 LLM 或更高级的 NLP 技术，这项指标应接近 **80-90%**。

### Revenue/Mile (每英里营收)
*   反映了调度算法的效率。
*   **注意**: 如果解析错误（地点错了），即使调度再好，这项指标也可能异常（因为车去了错误的地方，或者根本没接到人）。

---

## 🛠️ 如何测试你自己的 Agent

1.  **创建 Agent 类**:
    继承 `WhiteAgentBase` 并实现 `parse_request` 和 `make_routing_decision` 方法。

    ```python
    from white_agent import WhiteAgentBase

    class MyCustomAgent(WhiteAgentBase):
        def parse_request(self, nl_request, vehicle_database):
            # Your LLM logic here
            pass
            
        def make_routing_decision(self, structured_request, vehicle_database):
            # Your optimization logic here
            pass
    ```

2.  **修改评估脚本**:
    在 `examples/evaluate_baselines.py` 中引入你的 Agent 并加入测试列表：

    ```python
    from my_agent import MyCustomAgent
    
    # ...
    
    agents = [
        DummyWhiteAgent(),
        RegexBaselineAgent(),
        MyCustomAgent(agent_name="MyLLMAgent") # Add your agent here
    ]
    ```

3.  **运行评估**:
    再次运行 `python3 examples/evaluate_baselines.py` 查看对比结果。
