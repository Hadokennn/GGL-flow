"""Phase 4 tests for GGL extraction/summarization helpers."""

from src.ggl.graph.extraction import extract_topics_from_messages
from src.ggl.graph.summarization import MAX_KEYPOINTS, MAX_SUMMARY_CHARS, build_knowledge_card


def test_build_knowledge_card_schema_and_limits():
    messages = [
        "这是第一条知识点",
        "这是第二条知识点",
        "例如：监督学习可以用于垃圾邮件分类",
        "常见误区：把相关性当因果",
    ] * 4
    card = build_knowledge_card("机器学习", messages)
    assert set(card.keys()) == {"summary", "keyPoints", "examples", "commonMistakes", "relatedConcepts"}
    assert isinstance(card["summary"], str)
    assert len(card["summary"]) <= MAX_SUMMARY_CHARS
    assert isinstance(card["keyPoints"], list)
    assert len(card["keyPoints"]) <= MAX_KEYPOINTS
    assert "机器学习" in card["relatedConcepts"]


def test_extract_topics_prefers_candidate_topics():
    msgs = ["我们今天聊监督学习和神经网络。"]
    topics = extract_topics_from_messages(msgs, candidate_topics=["监督学习", "线性代数"])
    assert topics == ["监督学习"]


def test_extract_topics_fallback_tokenization():
    msgs = ["这是一个新的主题：概率统计 与 贝叶斯推断。"]
    topics = extract_topics_from_messages(msgs)
    assert len(topics) > 0

