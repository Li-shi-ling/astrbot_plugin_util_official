from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PLUGIN_ROOT / "main.py"


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("qqofficial_util_main", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeMessageObj:
    raw_message = {}
    self_id = "qq_official"


class FakeEvent:
    def __init__(self, module, messages, text, platform="qq_official"):
        self._module = module
        self._messages = messages
        self._text = text
        self._platform = platform
        self.message_obj = FakeMessageObj()

    def get_platform_name(self):
        return self._platform

    def get_messages(self):
        return self._messages

    def get_message_str(self):
        return self._text

    def get_self_id(self):
        return "qq_official"


def make_plugin(module):
    return object.__new__(module.QQOfficialUtilPlugin)


def test_qqofficial_box_requires_bot_at_marker():
    module = load_plugin_module()
    plugin = make_plugin(module)
    event = FakeEvent(
        module,
        [module.Comp.At(qq="qq_official"), module.Comp.Plain("盒 123456789")],
        "盒 123456789",
    )

    assert plugin._extract_box_command_text(event) == "盒 123456789"

    without_at = FakeEvent(module, [module.Comp.Plain("盒 123456789")], "盒 123456789")
    assert plugin._extract_box_command_text(without_at) is None

    wrong_platform = FakeEvent(
        module,
        [module.Comp.At(qq="qq_official"), module.Comp.Plain("盒 123456789")],
        "盒 123456789",
        platform="aiocqhttp",
    )
    assert plugin._extract_box_command_text(wrong_platform) is None


def test_qqofficial_box_accepts_leading_blank_before_bot_at():
    module = load_plugin_module()
    plugin = make_plugin(module)
    event = FakeEvent(
        module,
        [
            module.Comp.Plain("   "),
            module.Comp.At(qq="qq_official"),
            module.Comp.Plain("盒 123456789"),
        ],
        "盒 123456789",
    )

    assert plugin._extract_box_command_text(event) == "盒 123456789"


def test_box_command_requires_space_and_digits():
    module = load_plugin_module()
    plugin = make_plugin(module)

    assert plugin._parse_box_target("盒 123456789") == "123456789"
    assert plugin._parse_box_target("  盒   123456789  ") == "123456789"
    assert plugin._parse_box_target("盒123456789") is None
    assert plugin._parse_box_target("盒 abc") is None
    assert plugin._parse_box_target("/盒 123456789") is None


def test_generated_output_omits_group_id():
    module = load_plugin_module()
    plugin = make_plugin(module)

    async def fake_location():
        return module.GeneratedLocation("测试省测试市测试区", None)

    plugin._generate_location = fake_location
    text, map_url = asyncio.run(plugin.generate_fake_dox("123456789"))

    assert map_url is None
    assert "账号：123456789" in text
    assert "群聊" not in text
    assert "group_openid" not in text
    assert "退群" not in text
