# Adding a New RCA Agent Framework

Goal: add a 7th framework (e.g. `myrca`) to the matrix. About **30 lines of code** in the new framework's repo + 1 entry in `.gitmodules`.

## Checklist

### 1. Fork the upstream agent repo

```bash
# On GitHub, fork the upstream agent repo to your org
# Then add as submodule:
git submodule add https://github.com/<your-org>/myrca.git frameworks/myrca
```

### 2. Mirror the ThinkDepthAI structure inside the agent repo

```
frameworks/myrca/
├── pyproject.toml                     # add entry-point (see below)
├── src/myrca/
│   ├── agent.py                      # core engine
│   ├── agents/eval_agent.py          # aegis v3 BaseAgent subclass
│   ├── prompts/agents/langgraph/rca.yaml   # ← COPY from thinkdepthai bit-for-bit
│   ├── prompts/manager.py            # PromptManager (copy from thinkdepthai)
│   ├── llm/factory.py                # LLM factory (copy from thinkdepthai, may need provider tweaks)
│   ├── converters.py                 # framework → v3 Trajectory
│   ├── tools.py / tools_lib/         # KEEP your own tool impl (the only framework-specific code)
│   └── config/{__init__,schema}.py   # YAML config loader (copy from thinkdepthai)
```

### 3. Implement the entry agent

`src/myrca/agents/eval_agent.py`:
```python
from rcabench_platform.v3.sdk.llm_eval.agents import BaseAgent
from rcabench_platform.v3.sdk.llm_eval.trajectory import Trajectory
from ..agent import MyRCAAgent as CoreAgent

class MyRCAEvalAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "myrca"

    async def run(self, incident: str, data_dir: str, **kwargs) -> "AgentResult":
        core = CoreAgent(config=...)
        return await core.run(input=incident, data_dir=data_dir, **kwargs)
```

### 4. Register via entry-point

`frameworks/myrca/pyproject.toml`:
```toml
[project.entry-points."llm_eval.agents"]
myrca = "myrca.agents.eval_agent:MyRCAEvalAgent"
```

After `pip install -e .`, verify:
```bash
uv run rca llm-eval show-agents | grep myrca
```

### 5. Write the trajectory converter

`src/myrca/converters.py` — produces `Trajectory(agent_trajectories=[AgentTrajectory(turns=[Turn(messages=[...])])])`.

For LangChain frameworks, you can reuse `TrajectoryConverter.from_langchain_messages()`.
For others, walk your framework's native message representation and emit Messages with `role`, `content`, `tool_calls`, etc.

For multi-agent frameworks, emit one main `AgentTrajectory(trajectory_id="main")` plus one per sub-agent (`sub_agent_call_id=...`), linking via `SubAgentCall.id ↔ sub_agent_call_id`.

### 6. Verify

```bash
# Run a smoke test on one ops-lite case
uv run rca llm-eval run config/eval/smoke.yaml -a myrca
```

Expected:
- `Trajectory.to_json()` written to PostgreSQL
- Dashboard can render the trajectory in CaseDetail
- `analysis/` modules (ngram / transitions / markov / radar) work on the new agent's data without code changes
