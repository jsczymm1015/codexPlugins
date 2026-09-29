# 导出系统导入模板一键生成

只提供 `list.html` 的绝对路径，插件从 `columns` 提取字段，使用内置的导入字段维护模板，在桌面生成 `模块名称.xlsx`。

## 使用

安装后新建一个 Codex 对话，选择此插件并发送：

> 根据这个 HTML 生成导入字段维护表：/项目绝对路径/templates/busi/example/list.html

Python 3.10+，依赖见 `requirements.txt`。技能会检查或准备独立环境；也可直接运行：

```sh
python3 -m venv ~/.cache/html-columns-excel/venv
~/.cache/html-columns-excel/venv/bin/python -m pip install -r requirements.txt
~/.cache/html-columns-excel/venv/bin/python scripts/export_fields.py /absolute/path/list.html
```

## 填写规则

保留模板第 1 行表头、第 2 行说明和默认值，从第 3 行写入。跳过“序号”，其他字段全部依次导出，包括隐藏列，不依赖 formatter 的显示转换。

| Excel 列 | 来源或固定值 |
|---|---|
| 字段编号、查询字段名称 | columns.field |
| 字段名称 | columns.title |
| 模块编号 | 导出地址 `/export?tplCd=...` 中 tplCd 值 |
| 模块名称 | `include :: header('...')` 中不含外围引号的名称 |
| 字段顺序 | 1 开始递增 |
| 字段加密类型、字段加密长度、字段加密开始位置 | 0 |
| 加密排除类型 | 1 |
| 展示类型 | 0 |
| 所属字段编号、所属字段名称、背景色、数据行说明 | 留空 |

静态解析，不执行输入页面。支持 JS 静态对象数组、嵌套数组、注释和 formatter 函数。无法明确解析的动态列、多个 columns/模块编号、缺少 field/title 等会报错，不生成不完整文件。同名目标文件存在时拒绝覆盖。模块名含非法文件名字符时停止，不擅自改名。只支持 UTF-8 HTML。

## 测试

```sh
python -m unittest discover -s tests -v
```

内置的 `assets/import-fields-template.xlsx` 是固定空白模板。参考成品、业务 HTML、截图和实际生成结果不随插件发布。

结构校验、合成单元测试与真实 HTML 端到端测试应分别记录；成功解析某个样例不代表支持任意动态 JavaScript。

## 交付验证（2026-09-29）

- 官方本地插件结构校验和 skill 元数据校验通过。
- 13 项合成单元测试通过，覆盖顺序、序号排除、formatter 忽略、模板保留、重复输出保护、公式文本与长表。
- 使用用户提供的真实 HTML 完成桌面 Excel 生成和回读：4 个字段；前 3 个字段逐单元格匹配参考成品，第 4 个字段为用户确认需要的“判责原因”。业务输入与输出不入库。
- 此验证覆盖脚本到 Excel；新对话中的自然语言触发由安装后加载技能提供。
