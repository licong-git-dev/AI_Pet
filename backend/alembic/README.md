# PetPal 数据库迁移指南

本项目使用 [Alembic](https://alembic.sqlalchemy.org/) 管理数据库迁移。

## 目录结构

```
alembic/
├── env.py           # 迁移环境配置
├── script.py.mako   # 迁移脚本模板
├── versions/        # 迁移版本文件
│   └── README.md
└── README.md        # 本文件
```

## 快速开始

### 1. 首次设置（新数据库）

```bash
cd backend

# 方法A: 使用 SQLAlchemy 创建所有表，然后标记基线
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
alembic stamp head

# 方法B: 运行所有迁移（从零开始）
alembic upgrade head
```

### 2. 首次设置（已存在数据库）

如果数据库中已有表，只需标记当前版本:

```bash
cd backend
alembic stamp head
```

## 常用命令

### 生成迁移

当模型有变化时，自动生成迁移脚本:

```bash
# 自动检测变化并生成迁移
alembic revision --autogenerate -m "Add new_field to users table"

# 手动创建空迁移（用于数据迁移等）
alembic revision -m "Data migration for xxx"
```

### 执行迁移

```bash
# 升级到最新版本
alembic upgrade head

# 升级到指定版本
alembic upgrade abc123

# 升级一个版本
alembic upgrade +1
```

### 回滚迁移

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade abc123

# 回滚所有（危险！）
alembic downgrade base
```

### 查看状态

```bash
# 查看当前版本
alembic current

# 查看迁移历史
alembic history

# 查看详细历史
alembic history --verbose

# 查看待执行的迁移
alembic heads
```

### 其他命令

```bash
# 标记当前数据库版本（不执行迁移）
alembic stamp <revision>

# 生成 SQL 脚本（不执行）
alembic upgrade head --sql > migration.sql
```

## 迁移最佳实践

### 1. 模型修改后立即生成迁移

```bash
# 修改 models/user.py 后
alembic revision --autogenerate -m "Add email_verified to users"
```

### 2. 检查生成的迁移脚本

自动生成的迁移可能不完美，请务必检查:
- 是否正确检测到所有变化
- 是否有需要手动处理的数据迁移
- 回滚操作是否正确

### 3. 测试迁移

```bash
# 升级
alembic upgrade head

# 回滚
alembic downgrade -1

# 再次升级确认可重复执行
alembic upgrade head
```

### 4. 数据迁移

对于需要迁移数据的场景，在 `upgrade()` 中添加:

```python
def upgrade():
    # 1. 添加新列（允许空值）
    op.add_column('users', sa.Column('new_field', sa.String(100), nullable=True))

    # 2. 迁移数据
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE users SET new_field = old_field WHERE old_field IS NOT NULL")
    )

    # 3. 如需要，设置非空约束
    op.alter_column('users', 'new_field', nullable=False)
```

## 多人协作

### 合并冲突处理

当多人同时创建迁移时，可能出现多个 head:

```bash
# 查看多个 head
alembic heads

# 创建合并迁移
alembic merge -m "Merge migrations" head1 head2
```

### 命名规范

迁移消息使用动词开头:
- `Add xxx to table` - 添加字段/表
- `Remove xxx from table` - 删除字段/表
- `Change xxx in table` - 修改字段
- `Create xxx table` - 创建表
- `Drop xxx table` - 删除表
- `Data migration for xxx` - 数据迁移

## 故障排除

### 问题: "Target database is not up to date"

```bash
# 查看当前状态
alembic current

# 升级到最新
alembic upgrade head
```

### 问题: 迁移脚本语法错误

检查 `versions/` 下最新的迁移文件，修复语法错误。

### 问题: 数据库和迁移版本不匹配

```bash
# 查看数据库记录的版本
alembic current

# 强制标记版本（谨慎使用）
alembic stamp <correct_revision>
```

## 生产环境部署

```bash
# 1. 备份数据库
mysqldump -u user -p database > backup.sql

# 2. 执行迁移
alembic upgrade head

# 3. 验证
alembic current
```

## 相关文档

- [Alembic 官方文档](https://alembic.sqlalchemy.org/en/latest/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
