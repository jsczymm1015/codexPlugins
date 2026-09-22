# Codex × Jev 功能测试助手

在 Codex 中调用本插件，把业务需求转成测试，执行并保留证据，再用 TypeSafe Jev 辅助检查用例覆盖和归类失败。适用于 Java/Spring、Python、JS/TS 等代码项目；实际测试工具由 Codex 根据项目选择。

## 使用

安装后在新任务中选择 **Codex × Jev 功能测试助手**，或输入：

> 用 $test-with-jev 验证这次功能改动。运行相关测试，让 Jev 辅助检查覆盖和失败原因，给出逐项结论。

> 用 Codex × Jev 测试这个接口的重复提交、权限和异常处理，先验证，不修改产品代码。

Codex 负责读取代码、设计和执行测试、核对 SQL/事务及实际断言。Jev 只接收精简、去标识化的需求和测试证据，返回辅助判断。Jev 不运行测试，不单独决定“功能通过”，不以模型判断替代真实断言。

## 安装

已有 `codex-plugins` marketplace：

```sh
codex plugin marketplace upgrade codex-plugins
codex plugin add codex-jev-test@codex-plugins
```

新电脑先执行：

```sh
codex plugin marketplace add https://github.com/jsczymm1015/codexPlugins.git
codex plugin add codex-jev-test@codex-plugins
```

安装后新建任务，以载入 skill。GitHub 分发不等于官方云端发布或账号自动同步。

## 配置 Jev

Python 3.10+，无 pip 依赖。使用 [TypeSafe 官方控制台](https://console.typesafe.ai/) 的 API Key。在自己的终端执行安装目录内：

```sh
python3 skills/test-with-jev/scripts/jev_test.py configure
python3 skills/test-with-jev/scripts/jev_test.py doctor
```

`configure` 隐藏输入，凭据保存到 `~/.config/codex-jev-test/api-key`，不进入插件、项目或 Git。也支持 `TYPESAFE_API_KEY`、`JEV_API_KEY` 或 `JEV_API_KEY_FILE`。请勿把密钥发给聊天。离线环境和缺少密钥时，Codex 仍可执行本地测试，报告会明确注明 Jev 未运行。

## 自测

在插件根目录：

```sh
python3 -m unittest discover -s tests -v
python3 skills/test-with-jev/scripts/jev_test.py analyze --input examples/evidence.json --dry-run
```

第一条包含输入校验、HTTP 协议模拟、有限重试、失败证据保留、密钥处理、JUnit 解析与 CLI 测试。第二条是无网络预览。它们不等于真实 Jev 服务端联调。

真实连通性检查（需密钥，使用合成示例，会产生提供商调用费用）：

```sh
python3 skills/test-with-jev/scripts/jev_test.py analyze --input examples/evidence.json
```

真实测试结果由项目测试框架产生；命令退出0仅代表插件处理完成，不表示业务测试通过。示例标记为 `not_run`，即使 API 调用成功也不能当成业务通过。

输入格式、报告字段和可选 JUnit 收集见 [usage.md](skills/test-with-jev/references/usage.md)。官方协议依据 [TypeSafe API reference](https://docs.typesafe.ai/api)，核对日期 2026-09-22。固定官方 HTTPS 端点、拒绝重定向、最多三次 HTTP 尝试；只处理用户明确提供的材料，不自动上传仓库或原始日志。
