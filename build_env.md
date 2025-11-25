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
设置API KEY

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

部署agentbeats 平台（检查端口 5173，9000，9001是否开放）：

```bash
agentbeats deploy --deploy_mode dev
```

如果能正常运行（没有退出），应该环境就没问题了，后面可以直接让Cursor 开始写