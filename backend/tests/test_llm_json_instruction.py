from types import SimpleNamespace

from app import llm
from app.schemas import SummaryOut


def test_json_mode_always_includes_json_instruction(monkeypatch):
    def completion(**kwargs):
        assert kwargs['response_format'] == {'type': 'json_object'}
        assert 'json' in kwargs['messages'][0]['content'].casefold()
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content='{"summary_en":"ok"}'))])
    monkeypatch.setattr(llm, '_json_mode', True)
    monkeypatch.setattr(llm, 'client', lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion))))
    monkeypatch.setattr(llm, '_log_usage', lambda *a: None)
    result = llm.chat_json(None, None, 'test', 'test-model', 'Extract the supplied facts.', [], SummaryOut, retries=0)
    assert result.summary_en == 'ok'
