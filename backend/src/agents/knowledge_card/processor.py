"""Knowledge card generator using LLM."""

import json
import logging
from pathlib import Path
from typing import Any

from src.agents.thread_state import GGLState, KnowledgeCard
from src.gateway.checkpoint_utils import get_checkpoint_tuple, persist_partial_state
from src.models import create_chat_model

logger = logging.getLogger(__name__)

_CARD_PROMPT = """你是一个学习助手，请根据以下对话记录，为已掌握的知识节点生成一张结构化知识卡片。

节点ID: {node_id}
节点名称: {node_label}

近期对话摘要（用于参考）：
{conversation}

请以 JSON 格式返回以下字段（无 markdown 代码块）：
{{
  "summary": "2-4句话的核心摘要",
  "keyPoints": ["关键知识点1", "关键知识点2", "...（3-7个）"],
  "examples": ["示例1", "示例2"],
  "commonMistakes": ["常见误区1", "常见误区2"],
  "relatedConcepts": ["相关概念1", "相关概念2"]
}}"""


def _format_messages(messages: list[Any]) -> str:
    """Format recent messages to text for LLM prompt, skipping injected context."""
    lines = []
    for msg in messages[-30:]:
        name = getattr(msg, "name", None)
        if name and name.startswith("ggl"):
            continue
        role = type(msg).__name__.replace("Message", "")
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in content
            )
        lines.append(f"[{role}] {str(content)[:300]}")
    return "\n".join(lines)


class KnowledgeCardProcessor:
    """Generates knowledge cards from conversation context via LLM."""

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name

    def _get_model(self):
        return create_chat_model(name=self._model_name, thinking_enabled=False)

    def generate(
        self,
        thread_id: str,
        node_id: str,
        node_label: str,
        messages: list[Any],
    ) -> bool:
        """Generate and persist a knowledge card. Returns True if successful."""
        try:
            conv_text = _format_messages(messages)
            prompt = _CARD_PROMPT.format(
                node_id=node_id,
                node_label=node_label,
                conversation=conv_text or "(无对话记录)",
            )

            model = self._get_model()
            response = model.invoke(prompt)
            response_text = str(response.content).strip()

            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )

            data = json.loads(response_text)
            card = KnowledgeCard(
                summary=data.get("summary", ""),
                keyPoints=data.get("keyPoints", []),
                examples=data.get("examples", []),
                commonMistakes=data.get("commonMistakes", []),
                relatedConcepts=data.get("relatedConcepts", []),
            )

            self._write_card_file(thread_id, node_id, node_label, card)
            self._update_checkpoint(thread_id, node_id, card)

            logger.info("Knowledge card generated: thread=%s node=%s", thread_id, node_id)
            return True

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response for card %s/%s: %s", thread_id, node_id, e)
            return False
        except Exception as e:
            logger.error("Knowledge card generation failed %s/%s: %s", thread_id, node_id, e)
            return False

    def _write_card_file(
        self, thread_id: str, node_id: str, node_label: str, card: KnowledgeCard
    ) -> None:
        """Write card to markdown file under thread outputs."""
        checkpoint_tuple = get_checkpoint_tuple(thread_id)
        if checkpoint_tuple is None:
            return
        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
        thread_data = channel_values.get("thread_data") or {}
        outputs_path = thread_data.get("outputs_path")
        if not outputs_path:
            return

        cards_dir = Path(outputs_path) / "knowledge_cards"
        cards_dir.mkdir(parents=True, exist_ok=True)

        lines: list[str] = [f"# {node_label}\n"]
        lines.append(f"## 摘要\n{card['summary']}\n")
        if card["keyPoints"]:
            lines.append("## 关键知识点")
            lines.extend(f"- {p}" for p in card["keyPoints"])
            lines.append("")
        if card["examples"]:
            lines.append("## 示例")
            lines.extend(f"- {e}" for e in card["examples"])
            lines.append("")
        if card["commonMistakes"]:
            lines.append("## 常见误区")
            lines.extend(f"- {m}" for m in card["commonMistakes"])
            lines.append("")
        if card["relatedConcepts"]:
            lines.append("## 相关概念")
            lines.extend(f"- {c}" for c in card["relatedConcepts"])
            lines.append("")

        (cards_dir / f"{node_id}.md").write_text("\n".join(lines), encoding="utf-8")
        logger.debug("Knowledge card file written: %s/%s.md", cards_dir, node_id)

    def _update_checkpoint(self, thread_id: str, node_id: str, card: KnowledgeCard) -> None:
        """Merge card + node_id into the full ggl state and persist."""
        checkpoint_tuple = get_checkpoint_tuple(thread_id)
        if checkpoint_tuple is None:
            logger.warning("Thread %s not found for checkpoint update", thread_id)
            return

        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
        current_ggl: GGLState | None = channel_values.get("ggl")

        # Build full merged ggl state to avoid overwriting topic_graph etc.
        merged_ggl: dict = dict(current_ggl or {})

        existing_cards: dict = dict(merged_ggl.get("knowledge_cards") or {})
        existing_cards[node_id] = card
        merged_ggl["knowledge_cards"] = existing_cards

        existing_ids: list[str] = list(merged_ggl.get("knowledge_card_node_ids") or [])
        if node_id not in existing_ids:
            existing_ids = existing_ids + [node_id]
        merged_ggl["knowledge_card_node_ids"] = existing_ids

        # Add knowledge card file to artifacts so it appears in the download list
        artifact_path = f"/mnt/user-data/outputs/knowledge_cards/{node_id}.md"
        existing_artifacts: list[str] = list(channel_values.get("artifacts") or [])
        if artifact_path not in existing_artifacts:
            existing_artifacts = existing_artifacts + [artifact_path]

        persist_partial_state(
            thread_id,
            {"ggl": merged_ggl, "artifacts": existing_artifacts},
        )
