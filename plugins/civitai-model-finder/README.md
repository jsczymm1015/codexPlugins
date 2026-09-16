# Civitai 模型寻址

Codex 技能插件：上传 Civitai / Stable Diffusion 原始 PNG，提取生成参数并查找模型资源下载地址。

## 使用

安装后新建 Codex 任务，启用本插件并上传 PNG。可只上传图片；如未自动触发，输入“查找这张 PNG 的模型下载地址”或 `$civitai-model-finder`。

输出主模型、LoRA、VAE、放大模型、明确声明的 Embedding 等依赖，含哈希、版本匹配状态、模型页、下载地址、ComfyUI 存放目录和原始参数 JSON。

支持 PNG tEXt / iTXt / zTXt（含压缩文本），A1111 parameters，以及常见 ComfyUI prompt/workflow 加载器。未知自定义节点会提示需要进一步检查。PNG 是生成参数载体，不包含模型权重。截图、转存图片可能没有元数据。

## 独立脚本

需要 Python 3.10+，无需 pip 安装依赖。在插件根目录运行：

```sh
python skills/civitai-model-finder/scripts/resolve_models.py "input.png" --lookup --output "models-report.json"
```

不传 `--lookup` 则仅本地解析。输出文件必须不存在，避免覆盖现有数据。退出码 0 表示提取/报告完成，不表示全部资源匹配；2 表示文件或解析失败。联网使用系统代理设置和 TLS 验证，单请求超时 12 秒、最多 4 并发、64 个查询，不无限重试。

CLI 自动查询哈希和少量明确的官方名称映射；名称搜索由 Codex 技能通过可用搜索/浏览工具完成。网络封锁、认证、限流、已下架模型可能阻止获取下载地址；状态会明确报告，绝不假称找到。

## 验证

```sh
python -m unittest discover -s tests -v
```

测试使用合成 PNG 和模拟 API，无需联网；不在插件中打包用户原图或生成参数报告。

## 安装与分享

本插件含 `.codex-plugin/plugin.json` 和 `skills/`，应将整个插件目录作为安装/分享单位。在本机 personal marketplace 注册后使用 `codex plugin add civitai-model-finder@personal`。在新电脑上需要重新注册/导入插件包；本地安装不会自动同步到云端。

## 数据与限制

图片在本地解析；查询仅发送哈希，搜索只用模型名称和哈希。JSON 报告包含原始元数据/提示词，请留在本地。不内置账号、密钥、用户图片或模型文件，不自动下载模型、不运行工作流。哈希匹配不等于免费、当前可下载或可完全复现原图。

参考：[Civitai 哈希查询接口](https://github.com/civitai/civitai-developer-docs/blob/main/site/reference/model-versions.md)、[Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)。
