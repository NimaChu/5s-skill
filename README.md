# 5S — 项目与工作空间整理技能

面向 Codex 等支持 SKILL.md 的 Agent。对当前项目执行盘点、结构整理、受控清理、历史归档、入口修正和验证，让当前位置清楚、历史可追溯、垃圾有依据、入口仍可用。

## 安装

将本仓库克隆到 Codex 的个人技能目录，目录名保留为 5s：

Windows PowerShell：

~~~powershell
git clone https://github.com/NimaChu/5s-skill.git "$env:USERPROFILE/.codex/skills/5s"
~~~

macOS / Linux：

~~~sh
git clone https://github.com/NimaChu/5s-skill.git ~/.codex/skills/5s
~~~

若该目录已存在，请先保存现有版本再选择合并或替换。自定义 CODEX_HOME 时，安装到对应的 skills/5s 目录。安装后重新开启 Codex 会话以加载技能。

## 使用

在绑定项目的聊天中说：

> 做下5S

也可以明确指定：

> 用 $5s 整理当前项目：盘点冗余、归档历史、修正引用并验证入口。

技能优先使用本次明确指定的目录，否则使用当前项目根目录，并遵守项目自身的 AGENTS.md 和目录约定。

## 内容

- [SKILL.md](SKILL.md)：完整工作流程与边界。
- [agents/openai.yaml](agents/openai.yaml)：技能名称、提示词与隐式调用配置。
- [references/helper-usage.md](references/helper-usage.md)：盘点、归档与恢复命令。
- [references/layout-decisions.md](references/layout-decisions.md)：结构迁移与兼容性判断。
- [scripts/workspace_5s.py](scripts/workspace_5s.py)：仅使用 Python 3.11+ 标准库的辅助工具。
- [scripts/check_workspace_5s.py](scripts/check_workspace_5s.py)：隔离临时目录中的安全自检。

## 辅助工具

~~~sh
python scripts/workspace_5s.py inventory /absolute/path/to/project
python scripts/workspace_5s.py archive /absolute/path/to/project old-build archive/old-build.zip
python scripts/workspace_5s.py restore /absolute/path/to/project archive/old-build.zip
~~~

盘点只读。归档和恢复默认预览／核验；添加 --apply 才执行。归档后还需显式添加 --remove-source，才在复核后删除源副本。执行开关不替代用户授权。

归档会校验文件大小与 SHA256，并保存空目录；拒绝链接、路径穿越、重复成员及覆盖不同内容。工具面向可静止的普通文件，不提供在线数据库一致性快照，不自动判断垃圾、停止服务或设置定时删除。

更多参数见[脚本用法](references/helper-usage.md)。

## 自检

~~~sh
python -B scripts/check_workspace_5s.py
~~~

测试使用独立临时目录，不整理实际项目。符号链接用例取决于主机是否允许创建链接；报告中的 skipped 应单独查看。

## 整理原则

遵循既有工具链和项目结构，保护源码、原始输入、当前发布、持久数据、配置和审计证据。未知资产先保留；迁移后验证引用、启动和构建入口。详细执行规则以 SKILL.md 为准。
