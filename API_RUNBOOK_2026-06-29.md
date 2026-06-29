# API_RUNBOOK_2026-06-29 — DeepSeek 连通性与实验复跑

## 结论

当前仓库侧的 DeepSeek 调用点在 `agent_nav.py`。本次已把 API 配置显式化，并新增 `scripts/deepseek_smoke.py`，用于在跑 100 题实验前先区分三类问题：

1. `DEEPSEEK_API_KEY` 没有进入当前进程。
2. 本地 DNS / 代理 / 防火墙导致 `api.deepseek.com` 不可达。
3. Key、余额、权限、模型名或限流问题。

注意：`APIConnectionError` 通常不是代码 recipe 或 trace 逻辑问题，而是网络层无法连到 API endpoint，或 TLS/proxy 失败。必须先让 smoke test 通过，再跑实验。

## DeepSeek 配置

仓库现在支持以下环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 无 | 必填。不要写入 repo。 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek OpenAI-compatible endpoint。 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 为了与旧 trace 可比，默认保留历史模型；新实验可设 `deepseek-v4-flash` 或 `deepseek-v4-pro`。 |
| `DEEPSEEK_TIMEOUT` | `70` | 主实验请求超时秒数；smoke test 默认 30。 |

## Windows PowerShell 设置方式

当前终端临时生效：

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
$env:DEEPSEEK_MODEL = "deepseek-chat"
```

持久写入用户环境变量，新开的终端生效：

```powershell
[Environment]::SetEnvironmentVariable('DEEPSEEK_API_KEY','sk-...','User')
[Environment]::SetEnvironmentVariable('DEEPSEEK_MODEL','deepseek-chat','User')
```

如果 Claude / VSCode 插件不是从这个终端启动的，它可能拿不到 `$env:DEEPSEEK_API_KEY`。要么在同一个终端里运行 Claude 命令，要么写入 User 环境变量后重启 VSCode。

## 必跑 smoke test

```bash
python scripts/deepseek_smoke.py
```

期望看到：

```text
[OK] DNS resolved api.deepseek.com: ...
[OK] API call succeeded. response='ok'
```

如果失败：

- `[FAIL] DEEPSEEK_API_KEY is not set`：key 没传进当前进程。
- `DNS/network cannot resolve`：本机网络/DNS/代理问题。
- `AuthenticationError` / `PermissionDeniedError`：key 或账号权限问题。
- `RateLimitError`：额度、余额或限流问题。
- `APIConnectionError` / `APITimeoutError`：网络、代理、防火墙、TLS 或 endpoint 临时问题。

## 复跑实验命令

先用当前 fixed code 复跑 baseline blind：

```bash
python exp_runner.py --n 100 --workers 8 --reveal none --out traces_fixed_100.json --eval
```

再跑 fixed reflection：

```bash
python exp_runner.py --n 100 --workers 8 --reveal none --reflect --out traces_fixed_reflect_100.json --eval
```

配对比较：

```bash
python exp_subset.py traces_blind_300.json traces_fixed_100.json
python exp_subset.py traces_relfam_p2_100.json traces_fixed_reflect_100.json
python exp_subset.py traces_fixed_100.json traces_fixed_reflect_100.json
```

## 验收标准

对照 `REPORT_NEXT.md` 与 `BASELINE_STATUS_2026-06-28.md`：

1. `first_last` 应恢复到接近 100%，因为 `skills/first_last/SKILL.md` 已强禁 `INDEX.md` / `by_year/`。
2. `before_last` 应恢复到 >=80%，因为跨年首尾必须扫全量 `data.txt`。
3. `reflect` 不应再出现 11 个 “正确答案 -> 知识库中无相关事实” 回归，因为空结果探针已从 `exp_runner.py` 移除。
4. P2 对 multi-answer 的 5 个改善应保留。
5. 如果 fixed reflection 仍低于 fixed baseline，说明“不完整信号”仍有误触发，需要进一步收紧 `_PLURAL_Q` 或仅允许 `_loaded_multianswer_skill(raw_steps)` 触发。

## Claude 可直接执行的指令

```text
请在仓库根目录执行：
1. python scripts/deepseek_smoke.py
2. 若 smoke 成功，执行：
   python exp_runner.py --n 100 --workers 8 --reveal none --out traces_fixed_100.json --eval
   python exp_runner.py --n 100 --workers 8 --reveal none --reflect --out traces_fixed_reflect_100.json --eval
   python exp_subset.py traces_blind_300.json traces_fixed_100.json
   python exp_subset.py traces_relfam_p2_100.json traces_fixed_reflect_100.json
   python exp_subset.py traces_fixed_100.json traces_fixed_reflect_100.json
3. 把 stdout 和生成的 traces_fixed_100.json / traces_fixed_reflect_100.json 汇总成 RESULTS_2026-06-29.md。
若 smoke 失败，不要跑实验；请贴出完整 smoke stdout，隐藏 key，只保留错误类型。
```
