"""
PetPal - SQL注入防护工具

提供SQL注入防护功能：
- 输入验证和清理
- 安全的动态查询构建
- 参数化查询辅助工具
- 危险模式检测

注意：本项目使用SQLAlchemy ORM，已有内置的SQL注入防护。
本模块提供额外的防护层，用于：
1. 原始SQL查询场景（应尽量避免）
2. 动态排序和分页
3. 搜索关键词过滤
4. 审计和日志记录
"""
import re
from typing import Optional, List, Dict, Any, Tuple, Union
from functools import wraps

from loguru import logger


# ==================== 危险模式定义 ====================

# SQL注入关键词（用于检测和告警）
SQL_INJECTION_KEYWORDS = [
    # 基础SQL关键词
    'select', 'insert', 'update', 'delete', 'drop', 'truncate',
    'create', 'alter', 'exec', 'execute',
    # 危险操作
    'union', 'join', 'having', 'group by', 'order by',
    # 条件绕过
    'or 1=1', 'or 1 = 1', "or '1'='1", 'or "1"="1"',
    'and 1=1', 'and 1 = 1', "and '1'='1",
    '1=1', '1 = 1', '2=2',
    # 注释
    '--', '/*', '*/', '#',
    # 特殊字符组合
    '; --', ';--', "' --", "'--",
    # 函数调用
    'char(', 'concat(', 'substring(', 'ascii(',
    'benchmark(', 'sleep(', 'waitfor',
    # 系统命令
    'xp_cmdshell', 'sp_executesql',
    # 信息获取
    'information_schema', 'sys.', 'sysobjects',
    'table_name', 'column_name',
    # 逻辑操作
    ' or ', ' and ', ' not ',
]

# 危险字符（用于简单过滤）
DANGEROUS_CHARS = [
    "'", '"', ';', '--', '/*', '*/',
    '\\', '\x00', '\n', '\r', '\x1a',
]

# 允许的排序方向
ALLOWED_ORDER_DIRECTIONS = {'asc', 'desc', 'ASC', 'DESC'}


# ==================== 输入验证 ====================

def is_safe_string(value: str, strict: bool = False) -> bool:
    """检查字符串是否安全

    Args:
        value: 要检查的字符串
        strict: 是否使用严格模式

    Returns:
        是否安全
    """
    if not value:
        return True

    value_lower = value.lower()

    # 检查危险关键词
    for keyword in SQL_INJECTION_KEYWORDS:
        if keyword in value_lower:
            logger.warning(f"检测到潜在SQL注入: keyword='{keyword}' in value='{value[:100]}'")
            return False

    if strict:
        # 严格模式：检查危险字符
        for char in DANGEROUS_CHARS:
            if char in value:
                logger.warning(f"检测到危险字符: char='{repr(char)}' in value='{value[:100]}'")
                return False

    return True


def detect_sql_injection(value: str) -> Tuple[bool, List[str]]:
    """检测是否包含SQL注入模式

    Args:
        value: 要检测的字符串

    Returns:
        (是否检测到注入, 匹配到的关键词列表)
    """
    if not value:
        return False, []

    value_lower = value.lower()
    detected = []

    for keyword in SQL_INJECTION_KEYWORDS:
        if keyword in value_lower:
            detected.append(keyword)

    if detected:
        logger.warning(
            f"SQL注入检测: 发现{len(detected)}个可疑模式, "
            f"keywords={detected}, value='{value[:200]}'"
        )

    return len(detected) > 0, detected


# ==================== 输入清理 ====================

def escape_sql_string(value: str) -> str:
    """转义SQL字符串中的特殊字符

    注意：这不是推荐的做法，应使用参数化查询。
    此函数仅用于日志记录等非查询场景。

    Args:
        value: 原始字符串

    Returns:
        转义后的字符串
    """
    if not value:
        return value

    # 转义特殊字符
    replacements = [
        ('\\', '\\\\'),
        ("'", "\\'"),
        ('"', '\\"'),
        ('\x00', ''),
        ('\n', '\\n'),
        ('\r', '\\r'),
        ('\x1a', ''),
    ]

    result = value
    for old, new in replacements:
        result = result.replace(old, new)

    return result


def sanitize_search_query(query: str, max_length: int = 100) -> str:
    """清理搜索查询字符串

    Args:
        query: 原始搜索查询
        max_length: 最大长度

    Returns:
        清理后的查询字符串
    """
    if not query:
        return ""

    # 去除首尾空白
    query = query.strip()

    # 限制长度
    if len(query) > max_length:
        query = query[:max_length]

    # 移除危险字符（保留基本搜索功能）
    # 只移除最危险的字符，保留中文等
    remove_chars = ["'", '"', ';', '--', '/*', '*/', '\\', '\x00']
    for char in remove_chars:
        query = query.replace(char, '')

    # 移除多余空格
    query = ' '.join(query.split())

    return query


def sanitize_identifier(identifier: str) -> str:
    """清理SQL标识符（表名、列名等）

    Args:
        identifier: 原始标识符

    Returns:
        清理后的标识符
    """
    if not identifier:
        return ""

    # 只允许字母、数字、下划线
    return re.sub(r'[^\w]', '', identifier)


# ==================== 安全查询构建 ====================

class SafeOrderBy:
    """安全的排序构建器

    用于构建安全的ORDER BY子句，防止SQL注入。
    """

    def __init__(self, allowed_columns: List[str]):
        """初始化

        Args:
            allowed_columns: 允许排序的列名列表
        """
        self.allowed_columns = {col.lower(): col for col in allowed_columns}

    def build(
        self,
        column: str,
        direction: str = 'desc',
        default_column: str = None,
    ) -> Tuple[Optional[str], str]:
        """构建安全的排序表达式

        Args:
            column: 请求的排序列
            direction: 排序方向 (asc/desc)
            default_column: 默认列（如果请求的列无效）

        Returns:
            (实际的列名, 排序方向)
        """
        # 验证排序方向
        direction = direction.lower() if direction else 'desc'
        if direction not in {'asc', 'desc'}:
            direction = 'desc'

        # 验证列名
        column_lower = column.lower() if column else ''
        if column_lower in self.allowed_columns:
            return self.allowed_columns[column_lower], direction

        # 使用默认列
        if default_column and default_column.lower() in self.allowed_columns:
            return self.allowed_columns[default_column.lower()], direction

        return None, direction


class SafePagination:
    """安全的分页构建器"""

    def __init__(
        self,
        max_page_size: int = 100,
        default_page_size: int = 20,
    ):
        self.max_page_size = max_page_size
        self.default_page_size = default_page_size

    def build(
        self,
        page: int = 1,
        page_size: int = None,
    ) -> Tuple[int, int, int]:
        """构建安全的分页参数

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            (offset, limit, 实际page_size)
        """
        # 验证页码
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 1
        page = max(1, page)

        # 验证每页数量
        if page_size is None:
            page_size = self.default_page_size
        else:
            try:
                page_size = int(page_size)
            except (TypeError, ValueError):
                page_size = self.default_page_size

        page_size = max(1, min(page_size, self.max_page_size))

        # 计算offset和limit
        offset = (page - 1) * page_size
        limit = page_size

        return offset, limit, page_size


class SafeQueryBuilder:
    """安全的动态查询构建器

    用于构建安全的动态SQL查询，防止SQL注入。
    注意：仅在必须使用原始SQL时使用，优先使用ORM。
    """

    def __init__(self):
        self.conditions: List[str] = []
        self.params: Dict[str, Any] = {}
        self._param_counter = 0

    def _next_param_name(self) -> str:
        """生成下一个参数名"""
        self._param_counter += 1
        return f"p{self._param_counter}"

    def add_equal(
        self,
        column: str,
        value: Any,
        column_whitelist: Optional[List[str]] = None,
    ) -> 'SafeQueryBuilder':
        """添加等于条件

        Args:
            column: 列名
            value: 值
            column_whitelist: 允许的列名列表

        Returns:
            self（支持链式调用）
        """
        if value is None:
            return self

        # 验证列名
        safe_column = sanitize_identifier(column)
        if column_whitelist and safe_column not in column_whitelist:
            raise ValueError(f"不允许的列名: {column}")

        param_name = self._next_param_name()
        self.conditions.append(f"{safe_column} = :{param_name}")
        self.params[param_name] = value

        return self

    def add_like(
        self,
        column: str,
        value: str,
        column_whitelist: Optional[List[str]] = None,
    ) -> 'SafeQueryBuilder':
        """添加LIKE条件

        Args:
            column: 列名
            value: 搜索值
            column_whitelist: 允许的列名列表

        Returns:
            self
        """
        if not value:
            return self

        safe_column = sanitize_identifier(column)
        if column_whitelist and safe_column not in column_whitelist:
            raise ValueError(f"不允许的列名: {column}")

        # 清理搜索值
        safe_value = sanitize_search_query(value)
        if not safe_value:
            return self

        param_name = self._next_param_name()
        self.conditions.append(f"{safe_column} LIKE :{param_name}")
        self.params[param_name] = f"%{safe_value}%"

        return self

    def add_in(
        self,
        column: str,
        values: List[Any],
        column_whitelist: Optional[List[str]] = None,
    ) -> 'SafeQueryBuilder':
        """添加IN条件

        Args:
            column: 列名
            values: 值列表
            column_whitelist: 允许的列名列表

        Returns:
            self
        """
        if not values:
            return self

        safe_column = sanitize_identifier(column)
        if column_whitelist and safe_column not in column_whitelist:
            raise ValueError(f"不允许的列名: {column}")

        # 为每个值创建参数
        param_names = []
        for value in values:
            param_name = self._next_param_name()
            param_names.append(f":{param_name}")
            self.params[param_name] = value

        self.conditions.append(f"{safe_column} IN ({', '.join(param_names)})")

        return self

    def add_range(
        self,
        column: str,
        min_value: Any = None,
        max_value: Any = None,
        column_whitelist: Optional[List[str]] = None,
    ) -> 'SafeQueryBuilder':
        """添加范围条件

        Args:
            column: 列名
            min_value: 最小值
            max_value: 最大值
            column_whitelist: 允许的列名列表

        Returns:
            self
        """
        safe_column = sanitize_identifier(column)
        if column_whitelist and safe_column not in column_whitelist:
            raise ValueError(f"不允许的列名: {column}")

        if min_value is not None:
            param_name = self._next_param_name()
            self.conditions.append(f"{safe_column} >= :{param_name}")
            self.params[param_name] = min_value

        if max_value is not None:
            param_name = self._next_param_name()
            self.conditions.append(f"{safe_column} <= :{param_name}")
            self.params[param_name] = max_value

        return self

    def add_raw_condition(
        self,
        condition: str,
        params: Dict[str, Any],
    ) -> 'SafeQueryBuilder':
        """添加原始条件（需谨慎使用）

        Args:
            condition: 条件字符串（必须使用命名参数）
            params: 参数字典

        Returns:
            self
        """
        # 检查条件是否安全
        if not is_safe_string(condition, strict=True):
            raise ValueError("检测到不安全的条件")

        self.conditions.append(condition)
        self.params.update(params)

        return self

    def build_where(self) -> Tuple[str, Dict[str, Any]]:
        """构建WHERE子句

        Returns:
            (WHERE子句, 参数字典)
        """
        if not self.conditions:
            return "", {}

        where_clause = " AND ".join(self.conditions)
        return f"WHERE {where_clause}", self.params

    def reset(self):
        """重置构建器"""
        self.conditions = []
        self.params = {}
        self._param_counter = 0


# ==================== 装饰器 ====================

def validate_sql_params(*param_names: str, strict: bool = False):
    """验证SQL参数的装饰器

    Args:
        param_names: 要验证的参数名
        strict: 是否使用严格模式

    Example:
        @validate_sql_params('keyword', 'username')
        def search_users(keyword: str, username: str):
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for param_name in param_names:
                if param_name in kwargs:
                    value = kwargs[param_name]
                    if isinstance(value, str) and not is_safe_string(value, strict):
                        raise ValueError(f"参数 {param_name} 包含不安全的内容")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def log_sql_query(func):
    """记录SQL查询的装饰器

    用于审计和调试
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 记录查询开始
        logger.debug(f"执行SQL查询: {func.__name__}")

        try:
            result = func(*args, **kwargs)
            logger.debug(f"SQL查询完成: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"SQL查询失败: {func.__name__}, error={e}")
            raise

    return wrapper


# ==================== 实用函数 ====================

def safe_like_pattern(value: str) -> str:
    """创建安全的LIKE模式

    转义LIKE中的特殊字符：%, _, [

    Args:
        value: 原始值

    Returns:
        安全的LIKE模式
    """
    if not value:
        return ""

    # 转义LIKE特殊字符
    value = value.replace('\\', '\\\\')
    value = value.replace('%', '\\%')
    value = value.replace('_', '\\_')
    value = value.replace('[', '\\[')

    return f"%{value}%"


def validate_table_name(table_name: str, allowed_tables: List[str]) -> bool:
    """验证表名是否在允许列表中

    Args:
        table_name: 表名
        allowed_tables: 允许的表名列表

    Returns:
        是否允许
    """
    if not table_name:
        return False

    return table_name.lower() in [t.lower() for t in allowed_tables]


def validate_column_names(
    columns: List[str],
    allowed_columns: List[str],
) -> List[str]:
    """验证并过滤列名

    Args:
        columns: 请求的列名列表
        allowed_columns: 允许的列名列表

    Returns:
        有效的列名列表
    """
    if not columns:
        return []

    allowed_set = {c.lower() for c in allowed_columns}
    return [c for c in columns if c.lower() in allowed_set]


# ==================== 服务类 ====================

class SQLGuard:
    """SQL注入防护服务类"""

    @staticmethod
    def is_safe(value: str, strict: bool = False) -> bool:
        """检查值是否安全"""
        return is_safe_string(value, strict)

    @staticmethod
    def detect(value: str) -> Tuple[bool, List[str]]:
        """检测SQL注入"""
        return detect_sql_injection(value)

    @staticmethod
    def escape(value: str) -> str:
        """转义SQL字符串"""
        return escape_sql_string(value)

    @staticmethod
    def sanitize_search(query: str, max_length: int = 100) -> str:
        """清理搜索查询"""
        return sanitize_search_query(query, max_length)

    @staticmethod
    def sanitize_id(identifier: str) -> str:
        """清理标识符"""
        return sanitize_identifier(identifier)

    @staticmethod
    def create_order_by(allowed_columns: List[str]) -> SafeOrderBy:
        """创建安全的排序构建器"""
        return SafeOrderBy(allowed_columns)

    @staticmethod
    def create_pagination(
        max_page_size: int = 100,
        default_page_size: int = 20,
    ) -> SafePagination:
        """创建安全的分页构建器"""
        return SafePagination(max_page_size, default_page_size)

    @staticmethod
    def create_query_builder() -> SafeQueryBuilder:
        """创建安全的查询构建器"""
        return SafeQueryBuilder()


# 全局实例
sql_guard = SQLGuard()
