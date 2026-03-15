"""Phase 6 MVP tests for GGL init/survey helpers."""

import pytest
from fastapi import HTTPException

from src.gateway.routers.ggl import _assert_version, _build_initial_topic_graph


def test_build_initial_topic_graph_shape():
    graph = _build_initial_topic_graph("机器学习")
    assert "nodes" in graph and "edges" in graph
    assert len(graph["nodes"]) >= 2
    root = graph["nodes"][0]
    assert root["id"] == "root"
    assert root["label"] == "机器学习"
    assert root["state"] == "exploring"


def test_assert_version_pass_when_match():
    _assert_version(expected_version=2, current_version=2)


def test_assert_version_raise_when_conflict():
    with pytest.raises(HTTPException) as exc:
        _assert_version(expected_version=1, current_version=2)
    assert exc.value.status_code == 409

