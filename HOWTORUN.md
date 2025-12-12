0. 
```bash
conda activate agentbeats
source .venv/bin/activate
export OPENROUTER_API_KEY='s'
export OPENAI_API_KEY='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'
```

1. deploy platform: agentbeats deploy --deploy_mode dev --backend_port 39000 --mcp_port 39001
2. run green agent: python agentbeats_adapter.py

3. See demo white agent baseline: python examples/evaluate_baselines.py

