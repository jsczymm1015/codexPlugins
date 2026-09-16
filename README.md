# 我的 Codex 插件

三个个人插件的源码与可安装 marketplace。

| 插件 | 标识 | 运行依赖 |
|---|---|---|
| 像素角色动画工坊 | `pixel-rpg-animator` | Codex 图像生成能力、用户角色参考图 |
| FrameRonin 本地素材工坊 | `frameronin-local` | Python、本机运行的 FrameRonin 后台 |
| Civitai 模型寻址 | `civitai-model-finder` | Python 3.10+、可访问 Civitai/搜索工具 |

## 在另一台电脑安装

先登录有权访问此 GitHub 仓库的账号，然后在装有 Codex CLI 的电脑运行：

```sh
codex plugin marketplace add https://github.com/jsczymm1015/codexPlugins.git
codex plugin add pixel-rpg-animator@codex-plugins
codex plugin add frameronin-local@codex-plugins
codex plugin add civitai-model-finder@codex-plugins
```

安装后新建 Codex 任务以加载技能。仓库同步的是插件文件，不会同时安装 FrameRonin 后台、大模型或其他运行依赖。仅登录同一个 Codex 账号不等于已配置此 Git marketplace。

更新目录：`codex plugin marketplace upgrade codex-plugins`，再按需重新安装更新后的插件。

## 目录与后续规则

`plugins/` 是插件源码；`.agents/plugins/marketplace.json` 是仓库目录。创建/更新插件测试通过后自动提交到本仓库，见 [AGENTS.md](AGENTS.md)。

## 本次验证范围

- 三个插件的官方格式校验与全部技能前置元数据校验。
- Civitai 模型寻址：28 项单元测试；此前已用用户原图验证解析及真实哈希查询。
- FrameRonin：客户端导入、合法/非法参数校验和 CLI 检查通过；本次 `127.0.0.1:8000` 连接被拒绝，后台未运行，因此未重做素材处理端到端测试。
- 像素角色动画工坊：技能结构及引用文件检查；此次上传不重新生成角色图集，不声称完成图像质量验收。

插件附带的 `gem18-reference.jpg` 为原插件使用的布局参考资源。用户输入图片、私人查询报告和模型权重不随本仓库上传。
