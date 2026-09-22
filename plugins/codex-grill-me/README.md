# Grill Me · Codex 深度追问助手

基于 [Matt Pocock skills](https://github.com/mattpocock/skills) 的 grill-me 和 grilling，保留分轮追问及决策依赖的核心方法。不是作者官方发行版。

## 使用

安装后在新任务选择本插件，或输入：

> 用 $grill-me 帮我把这个想法问透：我想做一个内部报销系统。先讨论，不写代码。

它会按前置决策分轮提问、给出建议并等待回答。可以随时说“一次只问一个”“缩小范围”“停止并汇总”。默认中文，不写文件、不改代码、不自行实施。

保留上游显式调用习惯，不自动把普通聊天变成追问。无需 Jev、API Key、MCP 服务或 Python 运行时；使用当前 Codex 模型及其已有工具。模型服务仍需正常可用，不保证离线推理。

## 安装

已有 codex-plugins 市场：

```sh
codex plugin marketplace upgrade codex-plugins
codex plugin add codex-grill-me@codex-plugins
```

新电脑从 GitHub 安装：

```sh
codex plugin marketplace add https://github.com/jsczymm1015/codexPlugins.git
codex plugin add codex-grill-me@codex-plugins
```

可迁移 ZIP：完整解压并保留隐藏目录，在含 .agents 的解压根目录执行：

```sh
codex plugin marketplace add .
codex plugin add codex-grill-me@codex-plugins
```

需要支持 plugin 命令的 Codex。若同名市场已存在，先核对来源；来自上述 GitHub 仓库时使用升级命令，不覆盖其他配置。安装后新建任务。ZIP 是固定版本快照，不是双击导入格式。GitHub 分发不是官方云端发布。

## 适配与验证

将上游入口及 grilling 合并为独立技能，移除 Claude 专用工具调用，事实检索不再强制子代理。保留上游显式调用策略，并增加用户停止、待验证项及实施授权边界。

结构校验与场景人工审查见 tests/acceptance.md；它们不等于真实多轮模型端到端测试。授权与来源见 NOTICE.md、LICENSE。
