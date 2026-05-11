"""
BTQL (BrainTrust Query Language) engine — Phase 1 implementation.

BTQL is a SQL-inspired query language for filtering and aggregating
traces, experiments, and scores. It provides a safe, parameterised
interface on top of SQLAlchemy so arbitrary user input can never
produce SQL injection.

Supported syntax (subset):
  SELECT <columns|*|aggregates>
  FROM   <traces|experiments|scores|datasets>
  WHERE  <conditions>        -- AND / OR, basic comparisons
  GROUP  BY <column>
  ORDER  BY <column> [ASC|DESC]
  LIMIT  <n>

Supported aggregates: COUNT(), AVG(), SUM(), MIN(), MAX()
Supported comparisons: =, !=, <, <=, >, >=, LIKE, IS NULL, IS NOT NULL, IN

Example queries:
  SELECT * FROM traces WHERE status = 'error' ORDER BY timestamp DESC LIMIT 50
  SELECT model, COUNT(*) as calls, AVG(latency_ms) FROM traces WHERE project_id = 'x' GROUP BY model
  SELECT * FROM traces WHERE environment = 'production' AND cost_usd > 0.01
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from database.models import Trace, Score, Experiment, Dataset


# ---------------------------------------------------------------------------
# Schema: Which columns are queryable per table
# ---------------------------------------------------------------------------

QUERYABLE_COLUMNS: Dict[str, Dict[str, Any]] = {
    "traces": {
        "id":                str,
        "project_id":        str,
        "model":             str,
        "status":            str,
        "environment":       str,
        "latency_ms":        float,
        "cost_usd":          float,
        "total_tokens":      int,
        "prompt_tokens":     int,
        "completion_tokens": int,
        "temperature":       float,
        "timestamp":         str,
        "created_at":        str,
        "error_message":     str,
    },
    "scores": {
        "id":           str,
        "trace_id":     str,
        "project_id":   str,
        "scorer_name":  str,
        "scorer_type":  str,
        "score_value":  float,
        "created_at":   str,
    },
    "experiments": {
        "id":          str,
        "project_id":  str,
        "name":        str,
        "status":      str,
        "model":       str,
        "avg_score":   float,
        "created_at":  str,
    },
    "datasets": {
        "id":            str,
        "project_id":    str,
        "name":          str,
        "version":       int,
        "example_count": int,
        "created_at":    str,
    },
}

TABLE_MAP = {
    "traces":      Trace,
    "scores":      Score,
    "experiments": Experiment,
    "datasets":    Dataset,
}

AGGREGATE_FUNCS = {
    "COUNT": func.count,
    "AVG":   func.avg,
    "SUM":   func.sum,
    "MIN":   func.min,
    "MAX":   func.max,
}

COMPARISON_OPS = {"=", "!=", "<", "<=", ">", ">=", "LIKE", "ILIKE"}


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------

@dataclass
class SelectColumn:
    raw: str                  # "model" or "COUNT(*)" or "AVG(latency_ms) as avg_lat"
    column: Optional[str]     # underlying column name (None for COUNT(*))
    aggregate: Optional[str]  # "COUNT", "AVG", etc.
    alias: Optional[str]      # user-supplied alias


@dataclass
class WhereCondition:
    column: str
    op: str
    value: Any


@dataclass
class BTQLQuery:
    table: str
    selects: List[SelectColumn] = field(default_factory=list)
    where: List[WhereCondition] = field(default_factory=list)
    where_logic: str = "AND"    # "AND" | "OR"
    group_by: Optional[str] = None
    order_by: Optional[str] = None
    order_dir: str = "DESC"
    limit: int = 100
    offset: int = 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_AGGR_RE = re.compile(
    r"^(COUNT|AVG|SUM|MIN|MAX)\(\s*(\*|[a-zA-Z_][a-zA-Z0-9_]*)\s*\)"
    r"(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?$",
    re.IGNORECASE,
)
_COL_ALIAS_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?$",
    re.IGNORECASE,
)


def _parse_select_column(raw: str) -> SelectColumn:
    raw = raw.strip()
    m = _AGGR_RE.match(raw)
    if m:
        aggr, col, alias = m.groups()
        return SelectColumn(
            raw=raw,
            column=None if col == "*" else col,
            aggregate=aggr.upper(),
            alias=alias,
        )
    m = _COL_ALIAS_RE.match(raw)
    if m:
        col, alias = m.groups()
        return SelectColumn(raw=raw, column=col, aggregate=None, alias=alias)
    raise ValueError(f"Cannot parse SELECT column: '{raw}'")


def _parse_value(raw: str) -> Any:
    """Convert a raw token string to a Python value."""
    raw = raw.strip()
    if (raw.startswith("'") and raw.endswith("'")) or \
       (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]
    if raw.upper() == "NULL":
        return None
    if raw.upper() == "TRUE":
        return True
    if raw.upper() == "FALSE":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# Tokenize WHERE clause respecting quoted strings and IN lists
_TOK_RE = re.compile(
    r"'[^']*'|\"[^\"]*\"|AND|OR|\bIS\s+NOT\s+NULL\b|\bIS\s+NULL\b"
    r"|ILIKE|LIKE|!=|<=|>=|[<>=!]|\bIN\b|\(|\)|[^\s,()]+",
    re.IGNORECASE,
)


def _parse_where(where_str: str) -> Tuple[List[WhereCondition], str]:
    """Parse a WHERE clause and return (conditions, logic_op)."""
    tokens = _TOK_RE.findall(where_str.strip())
    conditions: List[WhereCondition] = []
    logic_ops: List[str] = []
    i = 0

    while i < len(tokens):
        tok = tokens[i].upper()

        if tok in ("AND", "OR"):
            logic_ops.append(tok)
            i += 1
            continue

        # Expect: column op value  OR  column IS [NOT] NULL
        col = tokens[i]
        if i + 1 >= len(tokens):
            break
        op_raw = tokens[i + 1].upper()

        if op_raw in ("IS NULL", "IS NOT NULL"):
            conditions.append(WhereCondition(column=col, op=op_raw, value=None))
            i += 2
            continue

        if op_raw not in COMPARISON_OPS and op_raw != "IN":
            i += 1
            continue

        if i + 2 >= len(tokens):
            break

        if op_raw == "IN":
            # Parse IN (...) list
            vals = []
            i += 3  # skip column, IN, (
            while i < len(tokens) and tokens[i] != ")":
                if tokens[i] != ",":
                    vals.append(_parse_value(tokens[i]))
                i += 1
            i += 1  # skip )
            conditions.append(WhereCondition(column=col, op="IN", value=vals))
        else:
            value = _parse_value(tokens[i + 2])
            conditions.append(WhereCondition(column=col, op=op_raw, value=value))
            i += 3

    logic = "AND"
    if logic_ops:
        logic = "OR" if "OR" in logic_ops else "AND"

    return conditions, logic


def parse_btql(query_str: str) -> BTQLQuery:
    """Parse a BTQL query string into a BTQLQuery AST."""
    # Normalise whitespace
    q = re.sub(r"\s+", " ", query_str.strip())

    # --- FROM ---
    from_m = re.search(r"\bFROM\s+(\w+)", q, re.IGNORECASE)
    if not from_m:
        raise ValueError("BTQL query must contain FROM clause")
    table = from_m.group(1).lower()
    if table not in TABLE_MAP:
        raise ValueError(f"Unknown table '{table}'. Allowed: {list(TABLE_MAP)}")

    # --- SELECT ---
    sel_m = re.search(r"\bSELECT\s+(.+?)\s+FROM\b", q, re.IGNORECASE | re.DOTALL)
    raw_sel = sel_m.group(1).strip() if sel_m else "*"

    if raw_sel.strip() == "*":
        selects = []  # means "all columns"
    else:
        selects = [_parse_select_column(s) for s in _split_top_level(raw_sel)]

    # --- WHERE ---
    where_conditions: List[WhereCondition] = []
    where_logic = "AND"
    where_m = re.search(r"\bWHERE\s+(.+?)(?:\s+(?:GROUP|ORDER|LIMIT|$))", q, re.IGNORECASE | re.DOTALL)
    if not where_m:
        # Try WHERE until end-of-string
        where_m2 = re.search(r"\bWHERE\s+(.+)$", q, re.IGNORECASE | re.DOTALL)
        if where_m2:
            where_conditions, where_logic = _parse_where(where_m2.group(1))
    else:
        where_conditions, where_logic = _parse_where(where_m.group(1))

    # --- GROUP BY ---
    grp_m = re.search(r"\bGROUP\s+BY\s+(\w+)", q, re.IGNORECASE)
    group_by = grp_m.group(1) if grp_m else None

    # --- ORDER BY ---
    ord_m = re.search(r"\bORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?", q, re.IGNORECASE)
    order_by = ord_m.group(1) if ord_m else None
    order_dir = (ord_m.group(2) or "DESC").upper() if ord_m else "DESC"

    # --- LIMIT / OFFSET ---
    lim_m = re.search(r"\bLIMIT\s+(\d+)", q, re.IGNORECASE)
    limit = min(int(lim_m.group(1)), 1000) if lim_m else 100

    off_m = re.search(r"\bOFFSET\s+(\d+)", q, re.IGNORECASE)
    offset = int(off_m.group(1)) if off_m else 0

    return BTQLQuery(
        table=table,
        selects=selects,
        where=where_conditions,
        where_logic=where_logic,
        group_by=group_by,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
        offset=offset,
    )


def _split_top_level(s: str) -> List[str]:
    """Split comma-separated items, ignoring commas inside parentheses."""
    parts, current, depth = [], [], 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

def _get_model_attr(model, col: str):
    """Get a SQLAlchemy column attribute from a model class, or raise ValueError."""
    allowed = QUERYABLE_COLUMNS.get(
        next((k for k, v in TABLE_MAP.items() if v is model), ""), {}
    )
    if col not in allowed:
        raise ValueError(f"Column '{col}' is not queryable on {model.__tablename__}")
    return getattr(model, col)


def execute_btql(
    db: Session,
    btql: BTQLQuery,
    project_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a parsed BTQLQuery and return results + metadata."""
    model = TABLE_MAP[btql.table]
    allowed_cols = QUERYABLE_COLUMNS[btql.table]

    # Validate WHERE columns
    for cond in btql.where:
        if cond.column not in allowed_cols:
            raise ValueError(f"Column '{cond.column}' is not queryable")

    # Build base query
    has_aggregates = any(s.aggregate for s in btql.selects)

    if not btql.selects or not has_aggregates:
        # Plain SELECT * or column list
        q = db.query(model)
    else:
        # Aggregate query
        sa_cols = []
        for sel in btql.selects:
            if sel.aggregate:
                aggr_fn = AGGREGATE_FUNCS[sel.aggregate]
                if sel.column:
                    col_attr = _get_model_attr(model, sel.column)
                    col_expr = aggr_fn(col_attr)
                else:
                    col_expr = aggr_fn()  # COUNT(*)
                if sel.alias:
                    col_expr = col_expr.label(sel.alias)
                sa_cols.append(col_expr)
            else:
                col_attr = _get_model_attr(model, sel.column)
                if sel.alias:
                    col_attr = col_attr.label(sel.alias)
                sa_cols.append(col_attr)
        q = db.query(*sa_cols)

    # Apply mandatory project_id filter (security: scope to current project)
    if project_id_filter and hasattr(model, "project_id"):
        q = q.filter(getattr(model, "project_id") == project_id_filter)

    # Apply WHERE conditions
    filters = []
    for cond in btql.where:
        if cond.column == "project_id" and project_id_filter:
            continue  # already filtered above
        col_attr = _get_model_attr(model, cond.column)
        if cond.op == "=":
            filters.append(col_attr == cond.value)
        elif cond.op == "!=":
            filters.append(col_attr != cond.value)
        elif cond.op == "<":
            filters.append(col_attr < cond.value)
        elif cond.op == "<=":
            filters.append(col_attr <= cond.value)
        elif cond.op == ">":
            filters.append(col_attr > cond.value)
        elif cond.op == ">=":
            filters.append(col_attr >= cond.value)
        elif cond.op in ("LIKE", "ILIKE"):
            filters.append(col_attr.ilike(cond.value))
        elif cond.op == "IS NULL":
            filters.append(col_attr.is_(None))
        elif cond.op == "IS NOT NULL":
            filters.append(col_attr.isnot(None))
        elif cond.op == "IN":
            filters.append(col_attr.in_(cond.value or []))

    if filters:
        from sqlalchemy import and_, or_
        combine = and_ if btql.where_logic == "AND" else or_
        q = q.filter(combine(*filters))

    # GROUP BY
    if btql.group_by:
        grp_col = _get_model_attr(model, btql.group_by)
        q = q.group_by(grp_col)

    # COUNT for total (only for non-aggregate queries)
    total = None
    if not has_aggregates:
        total = q.count()

    # ORDER BY
    if btql.order_by:
        ord_col = _get_model_attr(model, btql.order_by)
        from sqlalchemy import asc, desc
        q = q.order_by(desc(ord_col) if btql.order_dir == "DESC" else asc(ord_col))

    # LIMIT / OFFSET
    q = q.limit(btql.limit).offset(btql.offset)

    # Execute and serialise
    rows = q.all()
    results = _serialise_rows(rows, btql, model)

    return {
        "table": btql.table,
        "total": total,
        "limit": btql.limit,
        "offset": btql.offset,
        "results": results,
        "columns": list(QUERYABLE_COLUMNS[btql.table].keys()),
    }


def _serialise_rows(rows, btql: BTQLQuery, model) -> List[Dict]:
    """Convert SQLAlchemy rows to plain dicts."""
    out = []
    has_aggregates = any(s.aggregate for s in btql.selects)

    for row in rows:
        if has_aggregates:
            # Row is a named tuple from query(*cols)
            if hasattr(row, "_asdict"):
                out.append(dict(row._asdict()))
            elif hasattr(row, "_fields"):
                out.append(dict(zip(row._fields, row)))
            else:
                out.append({"value": row})
        else:
            # Row is an ORM model instance
            d = {}
            for col in QUERYABLE_COLUMNS[btql.table]:
                val = getattr(row, col, None)
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                elif hasattr(val, "__float__"):
                    val = float(val)
                d[col] = val
            out.append(d)
    return out
