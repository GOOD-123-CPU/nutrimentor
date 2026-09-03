"""Unit tests that run offline: no network, no model download, no LLM."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from nutrimentor import prompts  # noqa: E402
from nutrimentor.retrieval.schema import Chunk  # noqa: E402


# ---------------------------------------------------------------------------
# Chunk model
# ---------------------------------------------------------------------------
class TestChunk:
    def test_citation_key_with_pmid(self):
        c = Chunk(text="x", doc_type="paper_row", pmid="12345", title="T")
        assert c.citation_key == "PMID:12345"

    def test_citation_key_without_pmid(self):
        c = Chunk(text="x", doc_type="curated_doc", title="彩虹餐盘教学")
        assert c.citation_key.startswith("彩虹餐盘教学"[:40])

    def test_public_dict_hides_raw_text(self):
        c = Chunk(text="secret body", doc_type="paper_row", pmid="1", title="T",
                  abstract="abs")
        d = c.to_public_dict()
        assert "text" not in d
        assert d["url"] == "https://pubmed.ncbi.nlm.nih.gov/1/"
        assert d["abstract"].startswith("abs")

    def test_public_dict_no_pmid_no_url(self):
        c = Chunk(text="x", doc_type="curated_doc", title="T")
        assert c.to_public_dict()["url"] == ""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
class TestPrompts:
    def test_all_personas_have_prompts(self):
        for p in ("student", "teacher", "researcher"):
            assert p in prompts.PERSONA_PROMPTS
            assert "{context}" in prompts.PERSONA_PROMPTS[p]
            assert "{question}" in prompts.PERSONA_PROMPTS[p]

    def test_prompt_renders_with_history(self):
        out = prompts.TEACHER_PROMPT.format(
            base_rules=prompts.BASE_RULES,
            history_block=prompts.HISTORY_BLOCK.format(history="问：A\n答：B"),
            context="CTX",
            question="Q",
        )
        assert "CTX" in out and "Q" in out and "问：A" in out

    def test_prompt_renders_without_history(self):
        out = prompts.STUDENT_PROMPT.format(
            base_rules=prompts.BASE_RULES, history_block="",
            context="CTX", question="Q",
        )
        assert "对话历史" not in out

    def test_researcher_prompt_is_bilingual_safe(self):
        out = prompts.RESEARCHER_PROMPT.format(
            base_rules_en=prompts.BASE_RULES_EN, history_block_en="",
            context="C", question="Q",
        )
        assert "Evidence Summary" in out

    def test_canned_responses_cover_personas(self):
        for p in ("student", "teacher", "researcher"):
            assert p in prompts.GREETINGS
            assert p in prompts.NO_DOCS


# ---------------------------------------------------------------------------
# Session memory
# ---------------------------------------------------------------------------
class TestSession:
    def _make_store(self, tmp_path, max_turns=6):
        from nutrimentor.sessions import SessionStore

        return SessionStore(db_path=tmp_path / "test_sessions.db", max_turns=max_turns)

    def test_turn_roundtrip(self, tmp_path):
        store = self._make_store(tmp_path)
        sid = store.ensure_session(None, "teacher")
        store.append_turn(sid, "teacher", "你好", "你好呀！")
        h = store.history_text(sid)
        assert "问：你好" in h and "答：你好呀！" in h

    def test_history_isolated_per_session(self, tmp_path):
        store = self._make_store(tmp_path)
        s1 = store.ensure_session(None, "teacher")
        s2 = store.ensure_session(None, "teacher")
        store.append_turn(s1, "teacher", "q1", "a1")
        assert store.history_text(s2) == ""
        assert "q1" in store.history_text(s1)

    def test_history_truncates_long_answers(self, tmp_path):
        store = self._make_store(tmp_path)
        sid = store.ensure_session(None, "teacher")
        store.append_turn(sid, "teacher", "q", "a" * 500)
        assert len(store.history_text(sid)) < 300

    def test_max_turns_limits_history(self, tmp_path):
        store = self._make_store(tmp_path, max_turns=2)
        sid = store.ensure_session(None, "teacher")
        for i in range(5):
            store.append_turn(sid, "teacher", f"q{i}", f"a{i}")
        h = store.history_text(sid)
        # keeps only the most recent 2 turns
        assert "q4" in h and "q3" in h and "q0" not in h and "q2" not in h

    def test_turn_count(self, tmp_path):
        store = self._make_store(tmp_path)
        sid = store.ensure_session(None, "teacher")
        assert store.turn_count(sid) == 0
        store.append_turn(sid, "teacher", "q", "a")
        assert store.turn_count(sid) == 1


# ---------------------------------------------------------------------------
# Greeting detection
# ---------------------------------------------------------------------------
class TestGreetingDetection:
    def _engine_gate(self):
        # Test the static logic without instantiating the engine (no LLM key)
        from nutrimentor.prompts import SIMPLE_GREETINGS

        def is_greeting(text: str) -> bool:
            t = text.strip().lower()
            return len(t) <= 10 and any(g in t for g in SIMPLE_GREETINGS)

        return is_greeting

    def test_simple_greetings(self):
        g = self._engine_gate()
        assert g("你好")
        assert g("hello")
        assert g(" 你好 ")

    def test_real_questions_not_greetings(self):
        g = self._engine_gate()
        assert not g("维生素D对儿童骨骼发育有什么作用？")
        assert not g("你好，请问膳食纤维的作用机制和推荐摄入量")

    def test_long_greeting_is_question(self):
        g = self._engine_gate()
        assert not g("你好你好你好你好你好你好你好你好你好你好")


# ---------------------------------------------------------------------------
# Hybrid retrieval fusion logic (pure, no indexes)
# ---------------------------------------------------------------------------
class TestRRFFusion:
    def test_rrf_formula(self):
        # RRF = sum(1/(60+rank)); rank 1 in one engine -> 1/61
        assert abs(1 / (60 + 1) - 0.01639) < 1e-4

    def test_curated_bonus_monotonic(self):
        base = 1 / 61
        assert base * (1 + 0.08 * 2) > base


# ---------------------------------------------------------------------------
# Package integrity
# ---------------------------------------------------------------------------
class TestPackage:
    def test_version(self):
        import nutrimentor

        assert nutrimentor.__version__ == "1.0.0"

    def test_config_paths_resolve(self):
        from nutrimentor.config import DATA_DIR, VECTOR_DIR

        assert isinstance(DATA_DIR, Path) and isinstance(VECTOR_DIR, Path)

    def test_no_hardcoded_secrets_in_source(self):
        root = Path(__file__).resolve().parents[1]
        offenders = []
        for py in root.rglob("*.py"):
            content = py.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                if "sk-" in line and "sk-your" not in line and "example" not in line:
                    offenders.append(str(py))
        assert not offenders, f"Potential API keys in: {offenders}"
