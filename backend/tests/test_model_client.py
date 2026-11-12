"""The real OpenAI client (stubbed transport, no network), env settings, and the fake model."""
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm import FakeModelClient, OpenAIClient
from app.schemas import CLASSIFICATION_SCHEMA


class StubCompletions:
    def __init__(self, content, usage):
        self.content, self.usage, self.kwargs = content, usage, None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(model="gpt-6.1-terra-2026-10-26", usage=self.usage,
                               choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def _openai(content, usage):
    client = OpenAIClient(api_key="sk-test-not-real", model="gpt-6.1-terra")   # constructing makes no request
    stub = StubCompletions(content, usage)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=stub))
    return client, stub


async def test_openai_client_requests_strict_structured_output():
    client, stub = _openai('{"x": 1}', SimpleNamespace(prompt_tokens=120, completion_tokens=30))
    res = await client.complete(step="classify", system="SYS", user="USER",
                                schema=CLASSIFICATION_SCHEMA, schema_name="classification")
    fmt = stub.kwargs["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True and fmt["json_schema"]["schema"] is CLASSIFICATION_SCHEMA
    assert stub.kwargs["model"] == "gpt-6.1-terra"
    assert stub.kwargs["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]
    assert (res.text, res.input_tokens, res.output_tokens) == ('{"x": 1}', 120, 30)


async def test_openai_client_tolerates_missing_usage_and_content():
    client, _ = _openai(None, None)
    res = await client.complete(step="s", system="", user="", schema={}, schema_name="n")
    assert (res.text, res.input_tokens, res.output_tokens) == ("", 0, 0)


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/tmp/x.db")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
    monkeypatch.setenv("OPENAI_MODEL", "my-model")
    monkeypatch.setenv("FD_TOKEN", "secret")
    monkeypatch.setenv("MODEL_PRICE_INPUT", "2.5")
    monkeypatch.setenv("MODEL_PRICE_OUTPUT", "10")
    s = Settings.from_env()
    assert (s.db_path, s.openai_api_key, s.openai_model, s.fd_token) == ("/tmp/x.db", "sk-abc", "my-model", "secret")
    assert s.prices["my-model"] == (Decimal("2.5"), Decimal("10"))
    assert s.prices["fake-model"] == (Decimal("2.5"), Decimal("10"))   # demo cost follows the configured model
    assert s.demo_mode is False


def test_settings_defaults_to_demo(monkeypatch):
    for k in ("OPENAI_API_KEY", "MODEL_PRICE_INPUT", "MODEL_PRICE_OUTPUT", "OPENAI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    s = Settings.from_env()
    assert s.demo_mode is True and s.openai_model == "gpt-6.1-terra"


# ---- the fake itself ----

async def test_fake_accepts_callables_and_records_calls():
    fake = FakeModelClient(responses={"classify": lambda user: {"echo": "PROP" in user}})
    res = await fake.complete(step="classify", system="s", user="PROP-2", schema={}, schema_name="c")
    assert json.loads(res.text) == {"echo": True}
    assert fake.calls[0].step == "classify"


async def test_fake_demo_flags_vague_notes():
    fake = FakeModelClient()
    res = await fake.complete(step="check_missing", system="", user="<note>\nvalve odd\n</note>",
                              schema={}, schema_name="c")
    findings = json.loads(res.text)["findings"]
    assert json.loads(res.text)["flagged"] is True and len(findings) == 2


async def test_fake_rejects_unknown_step():
    with pytest.raises(ValueError):
        await FakeModelClient().complete(step="mystery", system="", user="", schema={}, schema_name="x")
