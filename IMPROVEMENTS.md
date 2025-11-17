# Agentic-AI 改进建议（基于当前整体流程）

本文档汇总了在使用 `fhvhv_tripdata_2025-01.parquet` 跑通完整 Green Agent 流程后，发现的可提升点。每一条都给出**现状**、**改进方向**和**增强原因**，方便后续按优先级逐步落地。

---

## 1. LLM 生成器初始化逻辑优化

- **现状**  
  `RequestSimulator` 在初始化时总是尝试创建 `LLMGenerator`，即使 `template_ratio=1.0` 完全不使用 LLM。若未配置 `OPENAI_API_KEY`，会打印 “LLM generator initialization failed”，然后降级为只用模板。

- **改进方向**  
  - 仅在 `template_ratio < 1.0` 且环境中存在对应 API Key 时才初始化 `LLMGenerator`。  
  - 无 API Key 时给出一次性、清晰的提示，而不是每次 demo 都打印错误栈。

- **增强原因**  
  - 减少不必要的外部依赖，提升 demo 的可移植性和稳定性。  
  - 降低日志噪音，避免让使用者误以为“流程出错”，而实际只是没启用 LLM。  
  - 为未来在无外网 / 无 Key 环境下的大规模评测打好基础。

---

## 2. Google Maps API 使用方式与 Key 管理

- **现状**  
  `LocationAugmenter` 初始化时会创建 Google Maps client，并提示 “Using hardcoded Google Maps API key”，即使当前 `augment_location=False` 也会走初始化逻辑。

- **改进方向**  
  - 将 Google Maps API Key 完全移出代码，改为从环境变量（如 `GOOGLE_MAPS_API_KEY`）读取。  
  - 仅在 `augment_location=True` 且 Key 存在时才初始化 Google Maps client。  
  - 若启用增强但缺少 Key，应给出明确错误或自动回退到“仅区级位置”的模式。

- **增强原因**  
  - 避免硬编码 Key 的安全风险，便于公开仓库和多人协作。  
  - 减少不必要的外部 API 调用，避免在 demo 或离线场景中引入隐性故障点。  
  - 更清晰地区分“基础模式”（无外部 API）和“全功能模式”（带地图增强）。

---

## 3. 请求模拟脚本的默认数据路径与参数化

- **现状**  
  `src/request_simulation/request_simulator.py` 中的 `main()` 默认将 parquet 文件路径设置为 `project_root.parent / "fhvhv_tripdata_2025-01.parquet"`，而当前实际数据文件位于仓库根目录 `Agentic-AI/fhvhv_tripdata_2025-01.parquet`。直接运行 `python -m request_simulation.request_simulator` 容易找不到数据。

- **改进方向**  
  - 将默认路径调整为仓库内的实际位置（例如：`project_root / "fhvhv_tripdata_2025-01.parquet"`）。  
  - 增加命令行参数或环境变量，允许用户显式指定 parquet 路径，而不依赖固定文件名和目录结构。

- **增强原因**  
  - 避免“能跑 demo_evaluation.py，但无法单独跑 request_simulator.main()”的路径不一致问题。  
  - 提升脚本可复用性，方便在不同数据集或路径结构下复用同一套模拟逻辑。  
  - 为后续集成到 pipeline / 调度平台时的自动化运行留出灵活性。

---

## 4. 车辆仿真时间推进与行程完成逻辑

- **现状**  
  在 `GreenAgentEnvironment.run_evaluation()` 中：  
  - 执行 `vehicle_simulator.execute_routing_decision()` 后，立即调用  
    `simulate_trip_completion(request_id, current_time + timedelta(minutes=30))`。  
  - 没有利用 `VehicleSimulator.advance_time()`，车辆不会真实经历“接客 → 行程中 → 完成”的时间演化，完成时间固定为请求时间 + 30 分钟。

- **改进方向**  
  - 引入统一的时间推进机制：  
    - 根据相邻请求的 `request_time` 差值调用 `advance_time()`，让车辆状态随时间变化。  
    - 行程完成时间基于 pickup 距离与 trip 距离估算（利用 `distance_calculator`），而不是固定 +30 分钟。  
  - 将 trip 完成触发逻辑从“立即完成”改为“到达预计 dropoff 时间后完成”。

- **增强原因**  
  - 更真实地模拟多请求、并行行程下的车辆占用，避免环境变成“每单都像是孤立静态问题”。  
  - 让“响应时间”“排队/等待”这类指标变得有意义，为复杂调度策略提供发挥空间。  
  - 为未来支持滚动调度、多轮决策打好基础。

---

## 5. White Agent 距离/时间估计与环境的一致性

- **现状**  
  - `DummyWhiteAgent.query_distance_and_time()` 使用简单的欧式距离 × 常数速度近似。  
  - `VehicleSimulator._default_distance_calculator()` 使用 Haversine 距离 + 固定 25 mph。  
  - `DummyWhiteAgent` 在 `RoutingDecision` 中将 `estimated_pickup_time`、`estimated_dropoff_time` 都设为 `request_time`，没有体现估计的行程时长。

- **改进方向**  
  - 为 White Agent 提供统一的距离/时间查询接口（例如通过 Green Agent 注入 `distance_calculator`），保证估计与环境模拟使用同一逻辑。  
  - 在 `RoutingDecision` 中使用估算出的 pickup/行程时间，填充合理的 `estimated_pickup_time` 与 `estimated_dropoff_time`。

- **增强原因**  
  - 保证“估计值 vs 实际模拟值”具有可比性，为将来的评估指标（例如 ETA 偏差）提供基础。  
  - 降低实现者心智负担：白盒 Agent 不需要重复实现一套距离估计逻辑。  
  - 避免估算值与模拟值差异过大，影响策略调参与结果解释。

---

## 6. 评分公式的参数化与基线对齐

- **现状**  
  - `Evaluator._calculate_overall_score()` 将总体得分定义为：  
    - 30%：解析准确度（四类准确率的平均值）  
    - 70%：路由效率，其中路由得分 = `net_revenue / 10` 截断到 `[0, 100]`。  
  - 当前是“硬编码示例公式”，未与任何基线策略（例如 DummyAgent 或 OR-Tools 最优路线）对齐。

- **改进方向**  
  - 将评分权重与归一化方式配置化（例如 `configs/evaluation.yaml`），而不是写死在代码中。  
  - 引入一个或多个基线策略（如 DummyAgent / 简单贪心 / OR-Tools），用基线表现来归一化路由得分（例如“相对基线提升”）。

- **增强原因**  
  - 避免“请求数变化导致净收入线性变大，路由得分迅速顶满”的问题，使不同规模实验具有可比性。  
  - 让评分标准更透明易调，便于根据实际业务重点（解析 vs 调度）调整权重。  
  - 为正式竞赛 / 论文结果提供更严谨的度量方式。

---

## 7. Demo Agent 与 Baseline Agent 体系

- **现状**  
  - `DummyWhiteAgent` 在解析阶段直接复制 ground truth，解析准确率始终为 100%，属于“作弊式” agent，仅用于验证 pipeline。  
  - 当前缺少一套“真实但简单”的 baseline Agent，用于对比参赛 Agent 的表现。

- **改进方向**  
  - 保留 `DummyWhiteAgent` 用于环境与日志调试，并在文档中明确标记为“仅限测试”。  
  - 增加 1–2 个非作弊 baseline：  
    - 例如只依赖模板文本的解析器；  
    - 或只根据 zone 名称/POI 粗略定位的解析器。  
  - 在 README 中展示“基线得分 vs 自定义 Agent 得分”的对比用法。

- **增强原因**  
  - 使评分结果有参照物，避免新 Agent 开发者不知道自己得分是“好还是坏”。  
  - 帮助验证解析模块本身的有效性，而不仅仅是验证 pipeline 是否能跑。  
  - 有利于未来将该框架用作公开 benchmark。

---

## 8. 请求模拟采样策略与大规模评估支持

- **现状**  
  - `GreenAgentEnvironment.generate_requests_from_data()` 中调用  
    `load_and_preprocess_data(parquet_path, sample_size=n_requests * 2)`，即默认只读取两倍请求数的数据。  
  - 适合小规模 demo，但在需要 1e4–1e5 级请求的评估时，可能需要更灵活的采样策略。

- **改进方向**  
  - 将 `sample_size` 暴露为参数，允许：  
    - 使用“全量数据”；  
    - 使用固定样本数；  
    - 或根据 parquet 规模自动调整。  
  - 在文档中给出不同数据规模下的推荐配置（如 `n_requests`、`sample_size`、`template_ratio`）。

- **增强原因**  
  - 方便从小规模 demo 平滑扩展到大规模离线评估，而不需要修改内部逻辑。  
  - 控制内存与计算成本，避免在大 parquet 上一次性加载过多数据。  
  - 提升整体系统在真实竞赛或生产环境中的可用性。

---

## 9. 统一的 CLI / 配置入口与使用体验

- **现状**  
  - 目前主要通过 `examples/demo_evaluation.py` 手动修改脚本参数来运行评估。  
  - 各种关键参数（车辆数量、请求数量、是否启用位置增强、评分参数等）分散在多个脚本中。

- **改进方向**  
  - 提供统一的 CLI 入口，例如：  
    - `python -m src.environment.run_eval --agent demo --n_requests 1000 --augment_location 0`  
  - 将关键超参集中在配置文件（如 `configs/evaluation.yaml`）中，CLI 只负责加载配置并覆盖少数参数。

- **增强原因**  
  - 降低新用户上手成本，“一条命令”即可跑完整评估。  
  - 有利于将整个框架嵌入到 CI/CD、批处理任务或外部调度系统中。  
  - 减少“复制修改 demo 脚本”带来的维护成本和潜在不一致。

---

> 以上各条可以独立实施，也可以按优先级依次推进。推荐顺序：  
> 1）先解决工程健壮性与配置化相关（第 1–3 条）；  
> 2）再增强仿真与评分逻辑（第 4–6 条）；  
> 3）最后完善 baseline 体系和用户体验（第 7–9 条）。  

