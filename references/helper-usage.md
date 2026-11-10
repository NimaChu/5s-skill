# 通用辅助脚本

`scripts/workspace_5s.py`仅依赖Python 3.11+标准库。替换下面的SKILL_DIR与PROJECT为实际绝对路径，清单写入项目已有的维护／验证目录。脚本不推断垃圾、不自动查进程、不停服务、不配置定时任务。

## 盘点（只读）

```text
python SKILL_DIR/scripts/workspace_5s.py inventory PROJECT
python SKILL_DIR/scripts/workspace_5s.py inventory PROJECT --root-allow AGENTS.md README.md --allow-dotfiles --output PROJECT/artifacts/maintenance/5s/inventory.json
```

统计一级目录体积／文件数、根文件、跳过的链接及读取错误。未传`--root-allow`就不推断白名单。默认只写stdout；`--output`才写报告，输出本身不计入统计。可重复`--skip`跳过明确无需深入的项目相对目录，报告标明范围。

## 归档静止文件或目录

```text
python SKILL_DIR/scripts/workspace_5s.py archive PROJECT relative/source archive/history/run.zip
python SKILL_DIR/scripts/workspace_5s.py archive PROJECT relative/source archive/history/run.zip --apply
python SKILL_DIR/scripts/workspace_5s.py archive PROJECT relative/source archive/history/run.zip --apply --remove-source
```

默认预览；第二条只归档，第三条才在ZIP内容校验、源集合及内容复核后移除原副本。源和目标均在PROJECT内，目标不能在源内；现有目标拒绝覆盖。外部归档位置由用户明确指定后，另用合适工具迁移并记录映射。

ZIP内`_5S_MANIFEST.json`为版本1清单：`source`是原项目相对路径，`files`记录原相对路径对应sha256／bytes／mode，`directories`包含原目录与空目录。保留内容、普通权限位和空目录；不承诺恢复ACL、所有者、扩展属性或在线数据一致性。既有项目其他格式继续用原工具，不改写旧清单冒充新格式。

## 恢复

```text
python SKILL_DIR/scripts/workspace_5s.py restore PROJECT archive/history/run.zip
python SKILL_DIR/scripts/workspace_5s.py restore PROJECT archive/history/run.zip --apply
```

默认核验；全部成员与碰撞预检通过后才创建缺失文件／目录。已有相同内容可复用；不同内容、文件／目录冲突、链接／junction、越界、重复或额外成员及损坏内容均报错。不自动覆盖或执行恢复出的代码。

工具拒绝盘符／文件系统根和整个用户主目录。归档拒绝链接和特殊文件；盘点记录并跳过。源正在变化时先取得生产者支持的一致快照，或保留原位。任何拒绝都不是删除兜底路径的授权。
