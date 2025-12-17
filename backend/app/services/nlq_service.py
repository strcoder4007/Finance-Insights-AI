from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import date
from typing import Any

from openai import OpenAI

from app.core.settings import Settings
from app.db import repo
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)


def _tool_result_summary(tool_name: str, result: Any) -> Any:
    if not isinstance(result, dict):
        if tool_name == "list_periods" and isinstance(result, list):
            return {"periods": len(result)}
        return result

    if tool_name == "query_metric":
        series = result.get("series") or []
        first_period = None
        last_period = None
        if isinstance(series, list) and series:
            if isinstance(series[0], dict):
                first_period = series[0].get("period")
            if isinstance(series[-1], dict):
                last_period = series[-1].get("period")
        return {
            "metric": result.get("metric"),
            "total": result.get("total"),
            "points": len(series) if isinstance(series, list) else None,
            "first_period": first_period,
            "last_period": last_period,
            "currency": result.get("currency"),
        }

    if tool_name == "query_breakdown":
        rows = result.get("rows") or []
        top = []
        if isinstance(rows, list):
            for r in rows[:5]:
                if isinstance(r, dict):
                    top.append({"name": r.get("name"), "value": r.get("value")})
        return {
            "category": result.get("category"),
            "total": result.get("total"),
            "rows": len(rows) if isinstance(rows, list) else None,
            "top": top,
            "currency": result.get("currency"),
        }

    if tool_name == "compare_periods":
        keys = ["metric", "period_a", "period_b", "a_value", "b_value", "delta_abs", "delta_pct", "currency"]
        return {k: result.get(k) for k in keys}

    return result


def _json_preview(value: Any, max_chars: int = 2500) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False)
    except TypeError:
        s = str(value)
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + f"...(+{len(s) - max_chars} chars)"


class NLQService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)

    def chat(self, conn: sqlite3.Connection, session_id: str | None, message: str) -> dict[str, Any]:
        session_id = session_id or str(uuid.uuid4())
        repo.ensure_chat_session(conn, session_id)
        repo.insert_chat_message(conn, session_id, "user", message)

        logger.info("nlq.chat session=%s user_message=%s", session_id, _json_preview(message, max_chars=400))

        history = repo.fetch_chat_messages(conn, session_id, limit=self.settings.chat_history_limit)
        history = list(reversed(history))

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "list_periods",
                    "description": "List available monthly periods.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_metric",
                    "description": "Get a metric time series and total over a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "group_by": {"type": "string", "enum": ["month", "quarter", "year"]},
                            "include_provenance": {"type": "boolean"},
                        },
                        "required": ["metric", "start_date", "end_date", "group_by"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_breakdown",
                    "description": "Get a category breakdown over a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "level": {"type": "integer", "minimum": 1, "maximum": 10},
                            "include_provenance": {"type": "boolean"},
                        },
                        "required": ["category", "start_date", "end_date", "level"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_periods",
                    "description": "Compare a metric between two period labels (e.g. 2024-Q1 vs 2024-Q2).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "period_a": {"type": "string"},
                            "period_b": {"type": "string"},
                            "include_provenance": {"type": "boolean"},
                        },
                        "required": ["metric", "period_a", "period_b"],
                    },
                },
            },
        ]

        system = (
            "You are a finance analyst assistant.\n"
            "Rules:\n"
            "- Never invent numbers; use tool outputs for all numeric claims.\n"
            "- If the question is ambiguous (metric, period, category), ask a clarifying question.\n"
            "- Keep answers concise and include 1-3 supporting facts.\n\n"
            "Allowed metrics:\n"
            "- revenue_total\n"
            "- cogs_total\n"
            "- gross_profit\n"
            "- operating_expenses_total\n"
            "- operating_profit\n"
            "- non_operating_revenue_total\n"
            "- non_operating_expenses_total\n"
            "- taxes_total\n"
            "- net_income\n\n"
            "Allowed breakdown categories:\n"
            "- revenue\n"
            "- cogs\n"
            "- operating_expense\n"
            "- non_operating_revenue\n"
            "- non_operating_expense\n"
            "- other_income\n"
            "- other_expense\n\n"
            "Date format: YYYY-MM-DD.\n"
            "Compare period labels: YYYY, YYYY-MM, or YYYY-Q1..YYYY-Q4.\n"
        )

        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})

        tool_calls_log: list[dict[str, Any]] = []
        supporting_data: dict[str, Any] = {}
        qs = QueryService(conn)

        def tool_list_periods() -> Any:
            periods = repo.list_periods(conn)
            return [
                {"period_start": p["period_start"], "period_end": p["period_end"], "currency": p["currency"]} for p in periods
            ]

        def tool_query_metric(args: dict[str, Any]) -> Any:
            res = qs.metric_timeseries(
                metric=args["metric"],
                start=date.fromisoformat(args["start_date"]),
                end=date.fromisoformat(args["end_date"]),
                group_by=args["group_by"],
                include_provenance=bool(args.get("include_provenance", False)),
            )
            supporting_data.setdefault("metrics", []).append(res)
            return res

        def tool_query_breakdown(args: dict[str, Any]) -> Any:
            res = qs.breakdown(
                category=args["category"],
                start=date.fromisoformat(args["start_date"]),
                end=date.fromisoformat(args["end_date"]),
                level=int(args["level"]),
                include_provenance=bool(args.get("include_provenance", False)),
            )
            supporting_data.setdefault("breakdowns", []).append(res)
            return res

        def tool_compare_periods(args: dict[str, Any]) -> Any:
            res = qs.compare_periods(
                metric=args["metric"],
                period_a=args["period_a"],
                period_b=args["period_b"],
                include_provenance=bool(args.get("include_provenance", False)),
            )
            supporting_data.setdefault("comparisons", []).append(res)
            return res

        name_to_func = {
            "list_periods": lambda a: tool_list_periods(),
            "query_metric": tool_query_metric,
            "query_breakdown": tool_query_breakdown,
            "compare_periods": tool_compare_periods,
        }

        for _ in range(8):
            resp = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                answer = msg.content or ""
                logger.info("nlq.answer session=%s answer=%s", session_id, _json_preview(answer, max_chars=800))
                repo.insert_chat_message(conn, session_id, "assistant", answer)
                return {
                    "session_id": session_id,
                    "answer": answer,
                    "supporting_data": supporting_data,
                    "tool_calls": tool_calls_log,
                }

            tool_calls_payload = []
            for tc in msg.tool_calls:
                tool_calls_payload.append(
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                )
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": tool_calls_payload})
            for tc in msg.tool_calls:
                fn = tc.function.name
                raw_args = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
                tool_calls_log.append({"name": fn, "arguments": args})
                logger.info("nlq.tool_call session=%s name=%s args=%s", session_id, fn, _json_preview(args))

                if fn not in name_to_func:
                    result = {"error": f"Unknown tool: {fn}"}
                else:
                    try:
                        result = name_to_func[fn](args)
                    except Exception as e:
                        result = {"error": str(e)}

                logger.info(
                    "nlq.tool_result session=%s name=%s summary=%s",
                    session_id,
                    fn,
                    _json_preview(_tool_result_summary(fn, result)),
                )
                logger.debug("nlq.tool_result_full session=%s name=%s result=%s", session_id, fn, _json_preview(result, max_chars=10000))

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )

        answer = "I couldn't complete the request within the tool call limit. Please rephrase or narrow the question."
        repo.insert_chat_message(conn, session_id, "assistant", answer)
        return {"session_id": session_id, "answer": answer, "supporting_data": supporting_data, "tool_calls": tool_calls_log}
