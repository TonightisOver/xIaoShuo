"""JSON 工具单元测试"""

from src.core.json_utils import (
    safe_json_parse,
    validate_json_structure,
)


class TestSafeJsonParse:
    """测试安全 JSON 解析"""

    def test_valid_json(self):
        """测试有效的 JSON"""
        json_str = '{"name": "张三", "age": 20}'
        result = safe_json_parse(json_str)
        assert result == {"name": "张三", "age": 20}

    def test_invalid_json_with_fallback(self):
        """测试无效 JSON 使用降级值"""
        json_str = "{invalid json"
        fallback = {"default": "value"}
        result = safe_json_parse(json_str, fallback=fallback)
        assert result == fallback

    def test_json_in_code_block(self):
        """测试代码块中的 JSON"""
        json_str = '''
        这是一些文本
        ```json
        {"name": "李四", "age": 25}
        ```
        更多文本
        '''
        result = safe_json_parse(json_str, extract_partial=True)
        assert result == {"name": "李四", "age": 25}

    def test_json_with_trailing_comma(self):
        """测试带尾部逗号的 JSON"""
        json_str = '{"name": "王五", "age": 30,}'
        result = safe_json_parse(json_str, extract_partial=True)
        assert result == {"name": "王五", "age": 30}

    def test_extract_partial_disabled(self):
        """测试禁用部分提取"""
        json_str = "Some text {\"name\": \"test\"} more text"
        fallback = {"fallback": True}
        result = safe_json_parse(json_str, fallback=fallback, extract_partial=False)
        assert result == fallback


class TestValidateJsonStructure:
    """测试 JSON 结构验证"""

    def test_valid_structure(self):
        """测试有效结构"""
        data = {"name": "张三", "age": 20, "city": "北京"}
        required_keys = ["name", "age"]
        assert validate_json_structure(data, required_keys) is True

    def test_missing_keys(self):
        """测试缺少键"""
        data = {"name": "张三"}
        required_keys = ["name", "age"]
        assert validate_json_structure(data, required_keys) is False

    def test_not_a_dict(self):
        """测试非字典类型"""
        data = ["not", "a", "dict"]
        required_keys = ["name"]
        assert validate_json_structure(data, required_keys) is False

    def test_empty_required_keys(self):
        """测试空的必需键列表"""
        data = {"name": "张三"}
        required_keys = []
        assert validate_json_structure(data, required_keys) is True
