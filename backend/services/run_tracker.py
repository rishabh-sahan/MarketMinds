"""Translate LangGraph state chunks into agent lifecycle events.

``MarketMindsGraph`` streams the full graph state after each node. That state
carries no explicit "agent X started / finished" signal — progress has to be
inferred from which report fields and debate histories have been populated.
This module owns that inference so the run service stays a thin transport
layer, and so the web UI's pipeline view reflects what is actually happening
instead of a fixed animation.

The inference mirrors the terminal CLI's live dashboard (``cli/main.py``):
an analyst is complete once its report field is non-empty, the first analyst
without a report is the one currently working, and the research / trading /
risk stages are driven by the debate-state dictionaries.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

# Analyst pipeline order and the state keys each one writes.
ANALYST_ORDER: Tuple[str, ...] = ("market", "social", "news", "fundamentals")

ANALYST_AGENT_NAMES: Dict[str, str] = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}

ANALYST_REPORT_KEYS: Dict[str, str] = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

# Agents that run after the analyst team, in pipeline order.
DOWNSTREAM_AGENTS: Tuple[str, ...] = (
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Trader",
    "Aggressive Analyst",
    "Conservative Analyst",
    "Neutral Analyst",
    "Portfolio Manager",
)

# Which report each downstream agent contributes to, for report_update events.
DOWNSTREAM_REPORT_KEYS: Dict[str, str] = {
    "Bull Researcher": "bull_history",
    "Bear Researcher": "bear_history",
    "Research Manager": "investment_plan",
    "Trader": "trader_investment_plan",
    "Aggressive Analyst": "aggressive_history",
    "Conservative Analyst": "conservative_history",
    "Neutral Analyst": "neutral_history",
    "Portfolio Manager": "final_trade_decision",
}

PENDING = "pending"
RUNNING = "running"
COMPLETED = "completed"


class RunTracker:
    """Derives agent status transitions and tool calls from streamed state.

    Call :meth:`ingest` with each chunk from the graph stream. It returns the
    events that the chunk newly implies — never a repeat of an event already
    emitted — so the caller can persist and broadcast them directly.
    """

    def __init__(self, selected_analysts: Iterable[str]):
        selected = [a for a in ANALYST_ORDER if a in set(selected_analysts)]
        # Fall back to the full team if the caller passed nothing recognisable,
        # so the pipeline view is never empty.
        self.selected_analysts: List[str] = selected or list(ANALYST_ORDER)

        self.agent_order: List[str] = [
            ANALYST_AGENT_NAMES[a] for a in self.selected_analysts
        ] + list(DOWNSTREAM_AGENTS)

        self.status: Dict[str, str] = {name: PENDING for name in self.agent_order}
        self.reports: Dict[str, str] = {}
        self._seen_message_ids: Set[str] = set()
        self._seen_tool_calls: Set[str] = set()

    # -- public API ---------------------------------------------------------

    def ingest(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fold one streamed state chunk in and return the new events."""
        events: List[Dict[str, Any]] = []
        events.extend(self._collect_tool_calls(chunk))
        events.extend(self._advance_analysts(chunk))
        events.extend(self._advance_research(chunk))
        events.extend(self._advance_trader(chunk))
        events.extend(self._advance_risk(chunk))
        return events

    def finish_all(self) -> List[Dict[str, Any]]:
        """Mark every remaining agent complete once the graph returns."""
        return [
            ev
            for name in self.agent_order
            for ev in self._set(name, COMPLETED)
        ]

    def snapshot(self) -> Dict[str, str]:
        """Current status of every agent in the pipeline."""
        return dict(self.status)

    # -- status transitions -------------------------------------------------

    def _set(self, agent: str, status: str) -> List[Dict[str, Any]]:
        """Move ``agent`` to ``status``, returning the implied events.

        Transitions only ever move forward (pending → running → completed), so
        a late chunk cannot walk an agent's state backwards.
        """
        if agent not in self.status:
            return []
        current = self.status[agent]
        if current == status or current == COMPLETED:
            return []
        if status == RUNNING and current != PENDING:
            return []

        events: List[Dict[str, Any]] = []
        # A jump straight to completed still needs its start event so the UI
        # can show the agent as having run rather than having been skipped.
        if status == COMPLETED and current == PENDING:
            self.status[agent] = RUNNING
            events.append({"type": "agent_start", "agent": agent})

        self.status[agent] = status
        events.append(
            {"type": "agent_start" if status == RUNNING else "agent_complete", "agent": agent}
        )
        return events

    def _report(self, agent: str, key: str, content: str) -> List[Dict[str, Any]]:
        """Record report content, returning an event only when it changed."""
        content = (content or "").strip()
        if not content or self.reports.get(key) == content:
            return []
        self.reports[key] = content
        return [
            {
                "type": "report_update",
                "agent": agent,
                "report_key": key,
                "report_content": content,
            }
        ]

    # -- stage handlers -----------------------------------------------------

    def _collect_tool_calls(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Emit a tool_call event for each newly seen tool invocation.

        ``stream_mode="values"`` replays the whole message history on every
        chunk, so messages are deduplicated by id before their tool calls are
        read off.
        """
        events: List[Dict[str, Any]] = []
        for message in chunk.get("messages") or []:
            msg_id = getattr(message, "id", None)
            if msg_id is not None:
                if msg_id in self._seen_message_ids:
                    continue
                self._seen_message_ids.add(msg_id)

            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                continue

            for call in tool_calls:
                if isinstance(call, dict):
                    name, args, call_id = call.get("name"), call.get("args", {}), call.get("id")
                else:
                    name = getattr(call, "name", None)
                    args = getattr(call, "args", {})
                    call_id = getattr(call, "id", None)
                if not name:
                    continue
                key = call_id or f"{name}:{args}"
                if key in self._seen_tool_calls:
                    continue
                self._seen_tool_calls.add(key)
                events.append(
                    {
                        "type": "tool_call",
                        "agent": self._current_agent(),
                        "tool": name,
                        "args": args if isinstance(args, dict) else {},
                    }
                )
        return events

    def _current_agent(self) -> str:
        """The agent presumed to own work happening right now."""
        for name in self.agent_order:
            if self.status[name] == RUNNING:
                return name
        return "system"

    def _advance_analysts(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analysts complete in order as their report fields fill in."""
        events: List[Dict[str, Any]] = []
        found_active = False

        for key in self.selected_analysts:
            agent = ANALYST_AGENT_NAMES[key]
            report_key = ANALYST_REPORT_KEYS[key]
            content = (chunk.get(report_key) or "").strip()

            if content:
                events.extend(self._report(agent, report_key, content))
                events.extend(self._set(agent, COMPLETED))
            elif self.reports.get(report_key):
                # Completed in an earlier chunk; nothing new to say.
                continue
            elif not found_active:
                events.extend(self._set(agent, RUNNING))
                found_active = True

        if not found_active:
            events.extend(self._set("Bull Researcher", RUNNING))
        return events

    def _advance_research(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Bull → Bear → Research Manager, driven by the debate state."""
        debate = chunk.get("investment_debate_state") or {}
        if not debate:
            return []

        events: List[Dict[str, Any]] = []
        bull = (debate.get("bull_history") or "").strip()
        bear = (debate.get("bear_history") or "").strip()
        judge = (debate.get("judge_decision") or "").strip()

        if bull:
            events.extend(self._report("Bull Researcher", "bull_history", bull))
            events.extend(self._set("Bull Researcher", RUNNING))
        if bear:
            events.extend(self._report("Bear Researcher", "bear_history", bear))
            events.extend(self._set("Bull Researcher", COMPLETED))
            events.extend(self._set("Bear Researcher", RUNNING))
        if judge:
            events.extend(self._report("Research Manager", "investment_plan", judge))
            events.extend(self._set("Bull Researcher", COMPLETED))
            events.extend(self._set("Bear Researcher", COMPLETED))
            events.extend(self._set("Research Manager", COMPLETED))
            events.extend(self._set("Trader", RUNNING))
        elif bear:
            events.extend(self._set("Research Manager", RUNNING))

        return events

    def _advance_trader(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """The trader is done as soon as its proposal appears."""
        plan = (chunk.get("trader_investment_plan") or "").strip()
        if not plan:
            return []
        events = self._report("Trader", "trader_investment_plan", plan)
        events.extend(self._set("Trader", COMPLETED))
        events.extend(self._set("Aggressive Analyst", RUNNING))
        return events

    def _advance_risk(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Risk committee rotates aggressive → conservative → neutral → PM."""
        risk = chunk.get("risk_debate_state") or {}
        if not risk:
            return []

        events: List[Dict[str, Any]] = []
        histories = (
            ("Aggressive Analyst", "aggressive_history"),
            ("Conservative Analyst", "conservative_history"),
            ("Neutral Analyst", "neutral_history"),
        )
        for agent, key in histories:
            content = (risk.get(key) or "").strip()
            if content:
                events.extend(self._report(agent, key, content))
                events.extend(self._set(agent, RUNNING))

        judge = (risk.get("judge_decision") or "").strip()
        if judge:
            for agent, _ in histories:
                events.extend(self._set(agent, COMPLETED))
            events.extend(self._report("Portfolio Manager", "final_trade_decision", judge))
            events.extend(self._set("Portfolio Manager", COMPLETED))
        return events
