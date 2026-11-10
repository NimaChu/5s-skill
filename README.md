# 5S — 通用项目与工作空间整理技能

适用于支持 SKILL.md 的 Agent，也可以由能读取文件、执行本地命令的 Agent 手动加载。核心流程与脚本不依赖 Codex API、MCP 或特定工具名。辅助脚本仅需要 Python 3.11+ 标准库。

一句话使用：

> 用5S技能整理当前项目：盘点冗余、安全清理可重建缓存、归档历史、修正引用并验证入口。

## 选择安装方式

| 使用环境 | 安装内容 | 调用 |
|---|---|---|
| WorkBuddy | 下载 Release 中的 WorkBuddy ZIP，通过「上传技能」导入 | 安装并启用后说「做下5S」或「用5S技能整理当前项目」 |
| Codex | 将仓库克隆到个人技能目录的 5s 子目录，或解压 portable ZIP | 普通中文请求，也保留 $5s 调用 |
| 其他支持 Agent Skills 的客户端 | 解压 portable ZIP，将完整 5s 目录放入该客户端实际支持的技能目录 | 按客户端技能选择方式或普通中文请求调用 |
| 没有技能自动发现的 Agent | 保留完整目录，明确要求 Agent 读取其中 SKILL.md | 同时指定要整理的项目绝对路径 |

自动发现和触发由宿主实现；不保证所有客户端识别同一种目录或调用语法。只读 Agent 可以盘点，实际整理需要本地读写与命令执行权限。

## WorkBuddy

1. 从 [v1.1.0 发布页](https://github.com/NimaChu/5s-skill/releases/tag/v1.1.0) 下载 **5s-workbuddy-1.1.0.zip**。
2. 在 WorkBuddy 的「专家·技能·连接器 → 技能」中，选择「添加技能 → 上传技能」，导入该 ZIP，并按客户端要求完成检查。
3. 在已安装列表中确认技能已启用，然后在目标项目聊天中说「用5S技能整理当前项目」；没有绑定项目时明确提供路径。

该包包含单个 5s/ 目录，内含 SKILL.md、references/ 和 scripts/。生成时为 SKILL.md 增补 WorkBuddy 开放平台要求的中英文展示字段、版本和作者；不携带 Codex 的界面配置。正文及执行脚本与通用版共用一份来源。

不要直接把 GitHub「Download ZIP」生成的 5s-skill-main 当作专用导入包；请使用 Release 附件。

依据：[WorkBuddy 官方上传说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)、[开放平台技能结构与字段](https://open.workbuddy.cn/docs/skill)。

## Codex

Windows PowerShell：

~~~powershell
git clone https://github.com/NimaChu/5s-skill.git "$env:USERPROFILE/.codex/skills/5s"
~~~

macOS / Linux：

~~~sh
git clone https://github.com/NimaChu/5s-skill.git ~/.codex/skills/5s
~~~

若目录已存在，先保存现有版本再选择合并或替换。自定义 CODEX_HOME 时安装到对应 skills/5s；安装后重新开启会话。agents/openai.yaml 仅供 Codex 显示和调用配置，其他 Agent 无需读取它。

## 其他 Agent / 手动加载

优先使用 [portable ZIP](https://github.com/NimaChu/5s-skill/releases/tag/v1.1.0)，保留名为 5s 的完整文件夹。实际安装位置以客户端文档为准，不把 .codex 当作通用目录。

若客户端不能自动发现技能，在对话中给出实际路径，例如：

> 请读取 /实际技能目录/5s/SKILL.md，按其中流程整理 /实际项目目录。先确认项目规则和保留物，再完成有依据的整理与验证。

技能内相对路径基于 SKILL.md 所在目录。项目目录与技能目录分别解析，避免误整理全局技能库。无需把 README 当作运行指令。

通用文件结构采用 [Agent Skills 规范](https://agentskills.io/specification) 的 name、description、Markdown 正文及相对资源路径。

## 资源与工具

- [SKILL.md](SKILL.md)：完整流程、宿主能力适配及权限边界。
- [references/helper-usage.md](references/helper-usage.md)：盘点、归档、恢复与含空格路径示例。
- [references/layout-decisions.md](references/layout-decisions.md)：结构迁移及兼容性判断。
- [scripts/workspace_5s.py](scripts/workspace_5s.py)：Python 标准库辅助工具。
- [scripts/check_workspace_5s.py](scripts/check_workspace_5s.py)：隔离临时目录中的安全自检。
- [scripts/package_skill.py](scripts/package_skill.py)：从同一来源生成两种发布包。

从仓库根目录运行；实际执行时可使用技能脚本的绝对路径：

~~~sh
python scripts/workspace_5s.py inventory /absolute/path/to/project
python scripts/workspace_5s.py archive /absolute/path/to/project old-build archive/old-build.zip
python scripts/workspace_5s.py restore /absolute/path/to/project archive/old-build.zip
~~~

python 应为已检查的 Python 3.11+，按环境替换成 python3 或 py -3；带空格路径需正确引用。命令默认预览或核验，--apply 才执行；归档后额外指定 --remove-source 才在复核后移除源文件。执行开关不能扩大用户授权或覆盖宿主审批。

保护源码、原始输入、当前发布、持久数据、配置和审计证据。归档检查大小与 SHA256，保存空目录，拒绝链接、路径穿越、重复成员及覆盖不同内容。工具处理可静止的普通文件，不提供在线数据库一致性快照。

## 验证与打包

~~~sh
python -B scripts/check_workspace_5s.py
python -B scripts/package_skill.py --version 1.1.0 --output dist
~~~

输出 portable 和 workbuddy 两个 ZIP 以及 SHA256 清单；已有同名文件拒绝覆盖。ZIP 使用固定时间戳，同一输入可重复生成相同内容。发布包只包含技能必需资源，不包含仓库历史、本机数据或构建缓存。

已完成：通用格式校验、WorkBuddy 必填字段与包结构检查、两种 ZIP 独立解压后的脚本安全自检、从非技能目录调用且路径含空格的只读盘点。验证环境为 Windows / Python 3.13。

尚未完成：WorkBuddy 客户端实际导入与自动触发验收、其他 Agent 和 macOS / Linux 客户端实测。格式适配和脚本验证不等同于这些客户端已经验收。
