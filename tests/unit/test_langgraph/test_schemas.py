"""validate_typed 与 langgraph schemas 单元测试。

验证 LLM 输出的 Pydantic 边界校验能拦截结构漂移（类型错误、字段缺失、
嵌套错误），并在失败时安全降级到 fallback。
"""
from __future__ import annotations

from src.core.json_utils import validate_typed
from src.core.langgraph.schemas import CharacterDesign, CharacterDesignResult


class TestValidateTyped:
    def test_valid_data_returns_model_instance(self):
        """合法数据返回 CharacterDesignResult 实例。"""
        data = {
            "characters": [
                {"name": "张三", "role": "主角", "personality": "坚韧"},
            ],
            "relationships": {"张三-李四": "师徒"},
        }
        result = validate_typed(data, CharacterDesignResult, "test")
        assert result is not None
        assert isinstance(result, CharacterDesignResult)
        assert len(result.characters) == 1
        assert result.characters[0].name == "张三"
        assert result.relationships == {"张三-李四": "师徒"}

    def test_missing_optional_fields_uses_defaults(self):
        """缺 role/personality 等可选字段时用默认值，不报错。"""
        data = {"characters": [{"name": "李四"}], "relationships": {}}
        result = validate_typed(data, CharacterDesignResult, "test")
        assert result is not None
        assert result.characters[0].name == "李四"
        assert result.characters[0].role == ""

    def test_characters_not_list_returns_fallback(self):
        """characters 是字符串而非数组时，返回 fallback。"""
        data = {"characters": "张三,李四", "relationships": {}}
        result = validate_typed(data, CharacterDesignResult, "test", fallback=None)
        assert result is None  # 校验失败

    def test_character_missing_name_returns_fallback(self):
        """角色缺 name 字段时返回 fallback。"""
        data = {"characters": [{"role": "主角"}], "relationships": {}}
        result = validate_typed(data, CharacterDesignResult, "test", fallback=None)
        assert result is None

    def test_relationships_not_dict_returns_fallback(self):
        """relationships 不是 dict 时返回 fallback。"""
        data = {"characters": [], "relationships": ["张三-李四"]}
        result = validate_typed(data, CharacterDesignResult, "test", fallback=None)
        assert result is None

    def test_returns_provided_fallback_on_failure(self):
        """校验失败时返回传入的 fallback 实例。"""
        fallback = CharacterDesignResult(characters=[], relationships={})
        data = {"characters": "not a list"}
        result = validate_typed(data, CharacterDesignResult, "test", fallback=fallback)
        assert result is fallback

    def test_extra_fields_ignored(self):
        """多余字段被忽略（extra=ignore），不报错。"""
        data = {
            "characters": [{"name": "张三"}],
            "relationships": {},
            "unexpected_field": "should be ignored",
        }
        result = validate_typed(data, CharacterDesignResult, "test")
        assert result is not None
        assert len(result.characters) == 1

    def test_empty_input_returns_fallback(self):
        """空 dict 输入：characters/relationships 有默认值，应通过。"""
        result = validate_typed({}, CharacterDesignResult, "test")
        assert result is not None
        assert result.characters == []
        assert result.relationships == {}

    def test_none_input_returns_fallback(self):
        """None 输入返回 fallback。"""
        result = validate_typed(None, CharacterDesignResult, "test", fallback=None)
        assert result is None


class TestCharacterDesignModel:
    def test_character_with_only_name(self):
        """CharacterDesign 只需 name。"""
        c = CharacterDesign(name="主角")
        assert c.name == "主角"
        assert c.role == ""
        assert c.ability == ""

    def test_character_full_fields(self):
        """全字段构造。"""
        c = CharacterDesign(
            name="张三", role="主角", personality="坚韧",
            background="平凡", goal="变强", ability="天赋",
        )
        assert c.role == "主角"
        assert c.ability == "天赋"
