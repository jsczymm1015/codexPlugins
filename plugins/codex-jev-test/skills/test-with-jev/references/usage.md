# 输入、命令与接口

以下命令中的 `SCRIPT` 表示本 skill 下 `scripts/jev_test.py` 的绝对路径。默认输出到 stdout，也可指定不存在的 `--output` 文件（拒绝覆盖）。支持 Python 3.10+，macOS、Linux、Windows。

## 准备与运行

```sh
python3 SCRIPT doctor
python3 SCRIPT analyze --input evidence.json --dry-run
python3 SCRIPT analyze --input evidence.json --output review.json
python3 SCRIPT collect --junit TEST-example.xml --output collected.json
```

`collect` 可重复 `--junit`。仅解析本次运行新生成的报告；它不运行命令，状态只是报告声明。补上 requirement ID 映射、预期及去标识化的实际摘要再交给 Jev。通用命令退出码由 Codex 如实写入 `runs`，非零退出码不会被 Jev 判定掩盖。

## 凭据

优先级：`TYPESAFE_API_KEY` → `JEV_API_KEY` → `JEV_API_KEY_FILE` 指定文件 → `~/.config/codex-jev-test/api-key`。

在自己的交互终端运行（输入隐藏，不写 shell 历史）：

```sh
python3 SCRIPT configure
```

默认文件保存在插件和项目目录之外；POSIX 权限为 0600，已有文件拒绝覆盖。Windows 建议使用进程环境变量；文件 ACL 由用户环境管理。`configure` 只接受交互终端输入。密钥从 [TypeSafe 控制台](https://console.typesafe.ai/) 获取；不要在聊天中提交。GUI 启动的 Codex 不一定继承 shell 环境，因此独立文件可供以后任务读取。撤销密钥请在提供商控制台完成。

## evidence.json

```json
{
  "requirements": [{"id": "R1", "text": "重复提交同一订单只能创建一条记录"}],
  "cases": [{
    "id": "C1",
    "requirement_ids": ["R1"],
    "scenario": "相同请求提交两次",
    "expected": "记录数为1",
    "observed": "隔离测试库中记录数为2",
    "status": "failed",
    "evidence": ["本次集成测试 assertCount 实际为2"]
  }],
  "runs": [{"command": "执行项目集成测试的实际命令", "exit_code": 1}]
}
```

状态仅允许 `passed`、`failed`、`error`、`skipped`、`not_run`。执行过的状态必须包含证据；脚本校验格式但不能证明用户输入的真实性。上层 Codex 必须核对实际命令和产物。`requirements` 最多20条，`cases` 最多100条，`runs` 最多20条；较大任务按业务模块拆分。单次请求最多64 KiB，不静默截断。未知字段拒绝，避免意外上传附带数据。

输出包括：输入摘要哈希、真实状态计数、确定性 `execution_status`（不是需求验收结论）、Jev 模型版本、官方 usage、覆盖提示和失败类别。覆盖为语义辅助判断，不能仅凭其标签宣称需求通过。置信度低于0.8或 unknown/insufficient 自动要求人工/ Codex 复核；阈值是插件工作流默认值，不是准确率保证。

`dry-run` 会展示脱敏后的完整请求，绝不联网，`jev_status=not_called`。无密钥的正式调用退出3；其他配置/格式/接口错误退出2。脚本成功退出0表示解析或评估完成，**不表示业务测试通过**，须读取 `execution_status` 和每个案例。

## 官方协议

2026-09-22 核对 [官方 API 文档](https://docs.typesafe.ai/api)。固定 HTTPS 端点 `https://api.typesafe.ai/v1/systemone`，Bearer 认证，默认 `jev-latest`（可用 `--model` 指定官方模型）。不支持任意 endpoint，不跟随重定向，防止凭据被转发。支持标准系统代理及证书校验，不降低 TLS 安全性。

请求由 `model`、`state`、`questions` 构成。本插件使用 Choice：需求覆盖 `covered/partial/missing/insufficient`，失败归类 `implementation/test/environment/data/unknown`。所有问题包含完整语义及对应 state 路径，互相独立。只请求实际需要的覆盖和失败判断。

返回逐项验证：问题 ID、类型、选项范围、概率分布、置信度和模型名。网络连接超时与 HTTP 429/5xx 有界重试；401、422及其他4xx不重试。错误只输出固定分类和 HTTP 状态，不输出服务器原始错误体或凭据。脱敏覆盖常见 token/password/header/email 等形式，但不能识别所有业务敏感数据；必须先提交精简的合成或去标识化摘要。
