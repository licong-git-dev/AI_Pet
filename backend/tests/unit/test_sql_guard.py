"""
PetPal - SQL注入防护单元测试
"""
import pytest
from app.utils.sql_guard import (
    is_safe_string, detect_sql_injection, escape_sql_string,
    sanitize_search_query, sanitize_identifier,
    SafeOrderBy, SafePagination, SafeQueryBuilder,
    validate_sql_params, safe_like_pattern,
    validate_table_name, validate_column_names,
    SQLGuard, sql_guard
)


class TestIsSafeString:
    """测试is_safe_string函数"""

    def test_safe_normal_string(self, safe_text_samples):
        """测试安全的普通字符串"""
        for text in safe_text_samples:
            assert is_safe_string(text)

    def test_detect_sql_keywords(self, sql_injection_samples):
        """测试检测SQL注入关键词"""
        for sample in sql_injection_samples:
            result = is_safe_string(sample)
            assert not result, f"Should detect injection in: {sample}"

    def test_empty_string(self):
        """测试空字符串"""
        assert is_safe_string('')
        assert is_safe_string(None) or is_safe_string('') == True

    def test_chinese_text(self):
        """测试中文文本"""
        assert is_safe_string('这是中文文本')
        assert is_safe_string('用户名：张三')

    def test_strict_mode(self):
        """测试严格模式"""
        # 包含单引号的字符串在严格模式下应该失败
        assert is_safe_string("It's fine", strict=False)
        assert not is_safe_string("It's fine", strict=True)


class TestDetectSqlInjection:
    """测试detect_sql_injection函数"""

    def test_detect_union_injection(self):
        """测试检测UNION注入"""
        detected, keywords = detect_sql_injection("1 UNION SELECT * FROM users")
        assert detected
        assert 'union' in keywords or 'select' in keywords

    def test_detect_comment_injection(self):
        """测试检测注释注入"""
        detected, keywords = detect_sql_injection("admin'--")
        assert detected
        assert '--' in keywords

    def test_detect_or_bypass(self):
        """测试检测OR绕过"""
        detected, keywords = detect_sql_injection("' OR '1'='1")
        assert detected

    def test_safe_string_no_detection(self):
        """测试安全字符串无检测"""
        detected, keywords = detect_sql_injection("Hello World")
        assert not detected
        assert len(keywords) == 0


class TestEscapeSqlString:
    """测试escape_sql_string函数"""

    def test_escape_single_quote(self):
        """测试转义单引号"""
        result = escape_sql_string("It's a test")
        assert "\\'" in result

    def test_escape_double_quote(self):
        """测试转义双引号"""
        result = escape_sql_string('Say "Hello"')
        assert '\\"' in result

    def test_escape_backslash(self):
        """测试转义反斜杠"""
        result = escape_sql_string('C:\\path')
        assert '\\\\' in result

    def test_remove_null_byte(self):
        """测试移除空字节"""
        result = escape_sql_string('test\x00data')
        assert '\x00' not in result


class TestSanitizeSearchQuery:
    """测试sanitize_search_query函数"""

    def test_normal_search(self):
        """测试普通搜索"""
        result = sanitize_search_query('hello world')
        assert result == 'hello world'

    def test_remove_dangerous_chars(self):
        """测试移除危险字符"""
        result = sanitize_search_query("test'; DROP TABLE--")
        assert "'" not in result
        assert '--' not in result

    def test_max_length(self):
        """测试最大长度"""
        long_query = 'a' * 200
        result = sanitize_search_query(long_query, max_length=100)
        assert len(result) <= 100

    def test_trim_whitespace(self):
        """测试去除首尾空白"""
        result = sanitize_search_query('  hello  ')
        assert result == 'hello'

    def test_chinese_search(self):
        """测试中文搜索"""
        result = sanitize_search_query('搜索关键词')
        assert result == '搜索关键词'


class TestSanitizeIdentifier:
    """测试sanitize_identifier函数"""

    def test_valid_identifier(self):
        """测试有效标识符"""
        assert sanitize_identifier('user_name') == 'user_name'
        assert sanitize_identifier('column1') == 'column1'

    def test_remove_special_chars(self):
        """测试移除特殊字符"""
        result = sanitize_identifier('user-name')
        assert '-' not in result

    def test_remove_spaces(self):
        """测试移除空格"""
        result = sanitize_identifier('user name')
        assert ' ' not in result

    def test_remove_sql_chars(self):
        """测试移除SQL字符"""
        result = sanitize_identifier('name; DROP')
        assert ';' not in result


class TestSafeOrderBy:
    """测试SafeOrderBy类"""

    def test_valid_column(self):
        """测试有效列名"""
        order_by = SafeOrderBy(['name', 'created_at', 'id'])
        column, direction = order_by.build('name', 'asc')
        assert column == 'name'
        assert direction == 'asc'

    def test_invalid_column(self):
        """测试无效列名"""
        order_by = SafeOrderBy(['name', 'created_at'])
        column, direction = order_by.build('password', 'asc')
        assert column is None

    def test_default_column(self):
        """测试默认列名"""
        order_by = SafeOrderBy(['name', 'created_at'])
        column, direction = order_by.build('invalid', 'asc', default_column='created_at')
        assert column == 'created_at'

    def test_invalid_direction(self):
        """测试无效排序方向"""
        order_by = SafeOrderBy(['name'])
        column, direction = order_by.build('name', 'invalid')
        assert direction == 'desc'  # 默认值

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        order_by = SafeOrderBy(['Name', 'Created_At'])
        column, direction = order_by.build('name', 'ASC')
        assert column is not None


class TestSafePagination:
    """测试SafePagination类"""

    def test_valid_pagination(self):
        """测试有效分页"""
        pagination = SafePagination()
        offset, limit, page_size = pagination.build(page=2, page_size=20)
        assert offset == 20
        assert limit == 20
        assert page_size == 20

    def test_negative_page(self):
        """测试负数页码"""
        pagination = SafePagination()
        offset, limit, page_size = pagination.build(page=-1)
        assert offset >= 0

    def test_max_page_size(self):
        """测试最大每页数量"""
        pagination = SafePagination(max_page_size=50)
        offset, limit, page_size = pagination.build(page_size=100)
        assert page_size <= 50

    def test_default_page_size(self):
        """测试默认每页数量"""
        pagination = SafePagination(default_page_size=15)
        offset, limit, page_size = pagination.build()
        assert page_size == 15

    def test_invalid_page_size_type(self):
        """测试无效的page_size类型"""
        pagination = SafePagination()
        offset, limit, page_size = pagination.build(page_size='invalid')
        assert isinstance(page_size, int)


class TestSafeQueryBuilder:
    """测试SafeQueryBuilder类"""

    def test_add_equal(self):
        """测试添加等于条件"""
        builder = SafeQueryBuilder()
        builder.add_equal('status', 1)
        where, params = builder.build_where()
        assert 'status = :' in where
        assert 1 in params.values()

    def test_add_like(self):
        """测试添加LIKE条件"""
        builder = SafeQueryBuilder()
        builder.add_like('name', 'test')
        where, params = builder.build_where()
        assert 'LIKE' in where
        assert any('%test%' in str(v) for v in params.values())

    def test_add_in(self):
        """测试添加IN条件"""
        builder = SafeQueryBuilder()
        builder.add_in('status', [1, 2, 3])
        where, params = builder.build_where()
        assert 'IN' in where
        assert len(params) == 3

    def test_add_range(self):
        """测试添加范围条件"""
        builder = SafeQueryBuilder()
        builder.add_range('age', min_value=18, max_value=65)
        where, params = builder.build_where()
        assert '>=' in where
        assert '<=' in where

    def test_chain_calls(self):
        """测试链式调用"""
        builder = SafeQueryBuilder()
        result = builder.add_equal('a', 1).add_equal('b', 2).add_like('c', 'test')
        assert result is builder
        where, params = builder.build_where()
        assert 'AND' in where

    def test_column_whitelist(self):
        """测试列名白名单"""
        builder = SafeQueryBuilder()
        with pytest.raises(ValueError):
            builder.add_equal('password', '123', column_whitelist=['name', 'email'])

    def test_reset(self):
        """测试重置"""
        builder = SafeQueryBuilder()
        builder.add_equal('status', 1)
        builder.reset()
        where, params = builder.build_where()
        assert where == ''
        assert len(params) == 0


class TestValidateSqlParams:
    """测试validate_sql_params装饰器"""

    def test_safe_params(self):
        """测试安全参数"""
        @validate_sql_params('keyword')
        def search(keyword: str):
            return keyword

        result = search(keyword='hello')
        assert result == 'hello'

    def test_unsafe_params(self):
        """测试不安全参数"""
        @validate_sql_params('keyword')
        def search(keyword: str):
            return keyword

        with pytest.raises(ValueError):
            search(keyword="'; DROP TABLE users; --")


class TestSafeLikePattern:
    """测试safe_like_pattern函数"""

    def test_escape_percent(self):
        """测试转义百分号"""
        result = safe_like_pattern('100%')
        assert '\\%' in result

    def test_escape_underscore(self):
        """测试转义下划线"""
        result = safe_like_pattern('user_name')
        assert '\\_' in result

    def test_wrap_with_percent(self):
        """测试包裹百分号"""
        result = safe_like_pattern('test')
        assert result.startswith('%')
        assert result.endswith('%')


class TestValidateTableName:
    """测试validate_table_name函数"""

    def test_valid_table(self):
        """测试有效表名"""
        assert validate_table_name('users', ['users', 'posts', 'comments'])

    def test_invalid_table(self):
        """测试无效表名"""
        assert not validate_table_name('passwords', ['users', 'posts'])

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert validate_table_name('USERS', ['users', 'posts'])


class TestValidateColumnNames:
    """测试validate_column_names函数"""

    def test_filter_valid_columns(self):
        """测试过滤有效列名"""
        columns = ['name', 'email', 'password']
        allowed = ['name', 'email', 'created_at']
        result = validate_column_names(columns, allowed)
        assert 'name' in result
        assert 'email' in result
        assert 'password' not in result

    def test_empty_input(self):
        """测试空输入"""
        result = validate_column_names([], ['name'])
        assert result == []


class TestSQLGuard:
    """测试SQLGuard类"""

    def test_singleton_instance(self):
        """测试单例实例"""
        assert sql_guard is not None
        assert isinstance(sql_guard, SQLGuard)

    def test_is_safe(self):
        """测试is_safe方法"""
        assert sql_guard.is_safe('hello world')
        assert not sql_guard.is_safe("'; DROP TABLE--")

    def test_detect(self):
        """测试detect方法"""
        detected, keywords = sql_guard.detect("UNION SELECT")
        assert detected

    def test_escape(self):
        """测试escape方法"""
        result = sql_guard.escape("It's test")
        assert "\\'" in result

    def test_create_order_by(self):
        """测试create_order_by方法"""
        order_by = sql_guard.create_order_by(['name', 'id'])
        assert isinstance(order_by, SafeOrderBy)

    def test_create_pagination(self):
        """测试create_pagination方法"""
        pagination = sql_guard.create_pagination()
        assert isinstance(pagination, SafePagination)

    def test_create_query_builder(self):
        """测试create_query_builder方法"""
        builder = sql_guard.create_query_builder()
        assert isinstance(builder, SafeQueryBuilder)
