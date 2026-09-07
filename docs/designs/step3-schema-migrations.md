# 设计：Schema 迁移机制

> 对应 `docs/ROADMAP.md` §5 与 §9.4（"迁移机制先于任何 schema 变更落地"）。
> 它本身不是路线图的编号步骤，而是第 2 步接线（给 `decision_points` 加 `ev_loss` 等列）的前置条件。

## 现状与问题

`init_db()` 里是十来段 `try: ALTER TABLE ... except OperationalError: pass`。单人开发够用，
但有三个问题：

1. **无法判断一个库处在什么版本**——只能靠"试着加列，失败就当已经有了"。
2. **无法拒绝降级**。用户跑了新版本再切回旧版本，旧代码会对着新 schema 静默读写。
3. **失败被吞掉**。`OperationalError` 不只有"列已存在"一种，磁盘只读、锁冲突同样被 `pass` 掉。

## 方案

`PRAGMA user_version` + 编号迁移列表。不引入 Alembic——SQLite 单文件、单机部署，
几十行代码足够，多一个依赖不划算。

```python
@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    apply: Callable[[aiosqlite.Connection], Awaitable[None]]
```

`migrate(db)` 读 `user_version`，按序执行大于它的迁移，每条成功后写入版本号并提交。

## 三个关键决定

**1. 版本 1 必须是幂等的。**
已有用户的库 `user_version = 0`，但里面可能已经有 `train_usable`、`experiment_id` 等列
（旧的 try/except 加过），也可能没有（更旧的库）。所以版本 1 = "把历史上那批 ALTER 重写成
带列存在性检查的操作"（`PRAGMA table_info` 先查再加）。新库跑到这里是空操作，因为
`_SCHEMA_SQL` 已经建全了。从版本 2 起可以写普通 DDL，靠 `user_version` 保证只跑一次。

**2. 库比程序新 → 拒绝启动。**
`user_version > SCHEMA_VERSION` 时抛 `SchemaVersionError`，而不是"尽力而为"。
静默降级读写是数据损坏的常见来源，宁可起不来。

**3. 每条迁移单独提交。**
中途失败时，已完成的迁移保持已应用且版本号正确，重启后从断点继续，而不是整批回滚重来。
SQLite 的 DDL 虽然可以在事务里，但逐条提交让"当前版本"始终是真话。

## 与 `_SCHEMA_SQL` 的分工

`_SCHEMA_SQL`（`CREATE TABLE IF NOT EXISTS`）继续负责**建库**，迁移只负责**改库**。
新库的路径是：建表（已含全部列）→ 迁移列表全部空跑 → 版本号打到最新。
这样新增一列时只需要两处同步：`_SCHEMA_SQL` 里的列定义 + 一条新迁移。

## 验证

- 新库：初始化后 `user_version == SCHEMA_VERSION`，重复 `init_db()` 幂等。
- 旧库：手工建一个缺列的 v0 库，跑 `init_db()` 后列补齐、版本号正确、数据不丢。
- 降级：把 `user_version` 设成一个更大的数，`init_db()` 必须抛 `SchemaVersionError`。
- 现有 386 个测试保持全绿（它们都走 `init_db()`）。
