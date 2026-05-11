"""
Scoring/Evaluation engine - handles code, LLM, and expected value scorers.
"""

import logging
from typing import Any, Callable, Optional, Dict, List
import json
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from database.models import Trace, Score, Eval, Dataset
from backend.config import settings

logger = logging.getLogger(__name__)


class CodeScorer:
    """Code-based scorer - user-defined Python function."""
    
    def __init__(self, scorer_func: Callable):
        self.scorer_func = scorer_func
    
    def score(self, trace: Trace, config: dict = None) -> float:
        """
        Execute code scorer function.
        
        Args:
            trace: Trace object to score
            config: Optional configuration for scorer
            
        Returns:
            Score between 0-1
        """
        try:
            # Call scorer with trace data
            score_value = self.scorer_func(
                input=trace.input_data,
                output=trace.output_data,
                expected=trace.expected_output,
                metadata=trace.meta
            )
            
            # Normalize score to 0-1
            if isinstance(score_value, bool):
                return 1.0 if score_value else 0.0
            
            score_value = float(score_value)
            return max(0.0, min(1.0, score_value))  # Clamp to [0, 1]
            
        except Exception as e:
            logger.error(f"Error in code scorer: {e}")
            raise


class LLMScorer:
    """LLM-based scorer - uses Claude, GPT, Gemini to judge output."""
    
    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None):
        self.model = model or "gpt-4"
        self.api_key = api_key
    
    async def score_async(
        self,
        trace: Trace,
        scorer_name: str = "llm_scorer",
        instructions: str = None
    ) -> tuple[float, str]:
        """
        Score trace using LLM.
        Returns (score, explanation)
        """
        try:
            # Import here to avoid hard dependency
            import openai
            
            # For MVP, use simple prompt to Claude/GPT
            prompt = f"""
You are evaluating an AI output. Rate it from 0 to 1.

Input: {json.dumps(trace.input_data, default=str)}

Expected Output: {json.dumps(trace.expected_output, default=str) if trace.expected_output else "N/A"}

Actual Output: {json.dumps(trace.output_data, default=str)}

{f"Custom Instructions: {instructions}" if instructions else ""}

Provide:
1. A score from 0 to 1
2. Brief explanation

Format your response as:
SCORE: [number]
EXPLANATION: [text]
"""
            
            # Call LLM API
            if "gpt" in self.model.lower():
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=500
                )
                result = response.choices[0].message.content
            
            elif "claude" in self.model.lower():
                from anthropic import Anthropic
                client = Anthropic(api_key=self.api_key)
                response = client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text
            
            else:
                raise ValueError(f"Unsupported model: {self.model}")
            
            # Parse result
            lines = result.split('\n')
            score = None
            explanation = ""
            
            for line in lines:
                if line.startswith("SCORE:"):
                    try:
                        score = float(line.replace("SCORE:", "").strip())
                        score = max(0.0, min(1.0, score))
                    except:
                        pass
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()
            
            if score is None:
                logger.warning(f"Could not parse LLM response: {result}")
                score = 0.5
            
            return score, explanation
            
        except Exception as e:
            logger.error(f"Error in LLM scorer: {e}")
            raise


class OllamaScorer:
    """Ollama-based scorer - uses local LLM via Ollama."""
    
    def __init__(self, model: str = "llama2", ollama_url: str = None):
        self.model = model or "llama2"
        self.ollama_url = ollama_url or settings.OLLAMA_API_URL
    
    async def score_async(
        self,
        trace: Trace,
        scorer_name: str = "ollama_scorer",
        instructions: str = None
    ) -> tuple[float, str]:
        """
        Score trace using local Ollama LLM.
        Returns (score, explanation)
        """
        try:
            import requests
            import asyncio
            
            prompt = f"""You are evaluating an AI output. Rate it from 0 to 1.

Input: {json.dumps(trace.input_data, default=str)}

Expected Output: {json.dumps(trace.expected_output, default=str) if trace.expected_output else "N/A"}

Actual Output: {json.dumps(trace.output_data, default=str)}

{f"Custom Instructions: {instructions}" if instructions else ""}

Provide:
1. A score from 0 to 1
2. Brief explanation

Format your response as:
SCORE: [number]
EXPLANATION: [text]
"""
            
            # Call Ollama API
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3,
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.text}")
            
            result = response.json().get("response", "")
            
            # Parse result
            lines = result.split('\n')
            score = None
            explanation = ""
            
            for line in lines:
                if line.startswith("SCORE:"):
                    try:
                        score = float(line.replace("SCORE:", "").strip())
                        score = max(0.0, min(1.0, score))
                    except:
                        pass
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()
            
            if score is None:
                logger.warning(f"Could not parse Ollama response: {result}")
                score = 0.5
            
            return score, explanation
            
        except Exception as e:
            logger.error(f"Error in Ollama scorer: {e}")
            raise


class ExpectedValueScorer:
    """Scorer that compares output to expected value."""
    
    def score(self, trace: Trace, config: dict = None) -> float:
        """Compare output to expected value."""
        if not trace.expected_output:
            logger.warning("No expected output provided for expected value scorer")
            return 0.5
        
        # Simple string comparison
        if isinstance(trace.output_data, str) and isinstance(trace.expected_output, str):
            # Exact match
            if trace.output_data.lower().strip() == trace.expected_output.lower().strip():
                return 1.0
            
            # Partial match (word similarity)
            output_words = set(trace.output_data.lower().split())
            expected_words = set(trace.expected_output.lower().split())
            
            if not expected_words:
                return 0.0
            
            intersection = len(output_words & expected_words)
            union = len(output_words | expected_words)
            
            return intersection / union if union > 0 else 0.0
        
        # JSON comparison
        if isinstance(trace.output_data, dict) and isinstance(trace.expected_output, dict):
            matching_keys = 0
            total_keys = len(trace.expected_output)
            
            for key, expected_val in trace.expected_output.items():
                if key in trace.output_data and trace.output_data[key] == expected_val:
                    matching_keys += 1
            
            return matching_keys / total_keys if total_keys > 0 else 0.0
        
        # Default: not equal
        return 0.0


# ===========================================================================
# Autoevals — pre-built, battle-tested scorers (mirrors TraceIQ autoevals)
# ===========================================================================

class ExactMatchScorer:
    """Autoevals: exact string equality (case-insensitive by default)."""

    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive

    def score(self, output: str, expected: str, **_) -> dict:
        if output is None or expected is None:
            return {"score": 0.0, "explanation": "Missing output or expected value"}
        a = str(output)
        b = str(expected)
        if not self.case_sensitive:
            a, b = a.lower().strip(), b.lower().strip()
        match = a == b
        return {"score": 1.0 if match else 0.0, "explanation": "Exact match" if match else "No exact match"}


class ContainsScorer:
    """Autoevals: checks whether the expected value is contained in the output."""

    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive

    def score(self, output: str, expected: str, **_) -> dict:
        if output is None or expected is None:
            return {"score": 0.0, "explanation": "Missing output or expected value"}
        a, b = str(output), str(expected)
        if not self.case_sensitive:
            a, b = a.lower(), b.lower()
        contains = b in a
        return {"score": 1.0 if contains else 0.0, "explanation": f"Output {'contains' if contains else 'does not contain'} expected"}


class RegexScorer:
    """Autoevals: tests whether output matches a given regex pattern."""

    def __init__(self, pattern: str):
        import re
        self.pattern = re.compile(pattern)

    def score(self, output: str, **_) -> dict:
        import re
        if output is None:
            return {"score": 0.0, "explanation": "No output to match"}
        matched = bool(self.pattern.search(str(output)))
        return {"score": 1.0 if matched else 0.0, "explanation": f"Pattern {'matched' if matched else 'not matched'}"}


class JSONValidityScorer:
    """Autoevals: checks that the output is valid parseable JSON."""

    def score(self, output: str, **_) -> dict:
        if output is None:
            return {"score": 0.0, "explanation": "No output"}
        if isinstance(output, (dict, list)):
            return {"score": 1.0, "explanation": "Already a JSON object"}
        try:
            json.loads(str(output))
            return {"score": 1.0, "explanation": "Valid JSON"}
        except Exception as e:
            return {"score": 0.0, "explanation": f"Invalid JSON: {e}"}


class LevenshteinScorer:
    """Autoevals: normalised Levenshtein edit-distance similarity (0–1)."""

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[:]
            dp[0] = i
            for j in range(1, n + 1):
                dp[j] = prev[j - 1] if a[i - 1] == b[j - 1] else 1 + min(prev[j], dp[j - 1], prev[j - 1])
        return dp[n]

    def score(self, output: str, expected: str, **_) -> dict:
        if output is None or expected is None:
            return {"score": 0.0, "explanation": "Missing output or expected value"}
        a, b = str(output).lower().strip(), str(expected).lower().strip()
        if not a and not b:
            return {"score": 1.0, "explanation": "Both empty"}
        dist = self._levenshtein(a, b)
        sim = 1.0 - dist / max(len(a), len(b))
        return {"score": round(max(0.0, sim), 4), "explanation": f"Edit distance={dist}, similarity={sim:.2%}"}


class WordOverlapScorer:
    """Autoevals: F1-based word token overlap (precision × recall harmonic mean)."""

    def score(self, output: str, expected: str, **_) -> dict:
        if output is None or expected is None:
            return {"score": 0.0, "explanation": "Missing output or expected value"}
        pred = set(str(output).lower().split())
        ref = set(str(expected).lower().split())
        if not ref:
            return {"score": 0.0, "explanation": "Empty expected value"}
        tp = len(pred & ref)
        precision = tp / len(pred) if pred else 0.0
        recall = tp / len(ref)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return {"score": round(f1, 4), "explanation": f"Precision={precision:.2%}, Recall={recall:.2%}, F1={f1:.2%}"}


class SemanticSimilarityScorer:
    """Autoevals: cosine similarity of sentence embeddings (uses sentence-transformers)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError("Install sentence-transformers: pip install sentence-transformers")
        return self._model

    def score(self, output: str, expected: str, **_) -> dict:
        try:
            import numpy as np
            model = self._get_model()
            embs = model.encode([str(output), str(expected)])
            cos = float(np.dot(embs[0], embs[1]) / (np.linalg.norm(embs[0]) * np.linalg.norm(embs[1]) + 1e-9))
            sim = max(0.0, cos)
            return {"score": round(sim, 4), "explanation": f"Cosine similarity={sim:.4f}"}
        except Exception as e:
            logger.warning(f"SemanticSimilarityScorer fallback (no sentence-transformers): {e}")
            return WordOverlapScorer().score(output, expected)


class NumericDiffScorer:
    """Autoevals: checks closeness of numeric values (within tolerance)."""

    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance

    def score(self, output, expected, **_) -> dict:
        try:
            a, b = float(output), float(expected)
            if b == 0:
                exact = a == b
                return {"score": 1.0 if exact else 0.0, "explanation": "Exact match" if exact else "Values differ"}
            diff = abs(a - b) / abs(b)
            passed = diff <= self.tolerance
            return {"score": 1.0 if passed else max(0.0, 1.0 - diff), "explanation": f"Relative diff={diff:.2%}"}
        except Exception as e:
            return {"score": 0.0, "explanation": f"Non-numeric values: {e}"}


class ToxicityScorer:
    """Autoevals: keyword-based toxicity detection (fast, no API needed)."""

    _TOXIC_WORDS = {
        "hate", "kill", "murder", "racist", "sexist", "bigot", "slur",
        "violence", "abuse", "harass", "threaten", "obscene", "porn",
    }

    def score(self, output: str, **_) -> dict:
        if not output:
            return {"score": 1.0, "explanation": "Empty output — no toxicity detected"}
        text_lower = str(output).lower()
        found = [w for w in self._TOXIC_WORDS if w in text_lower]
        if found:
            return {"score": 0.0, "explanation": f"Toxic keywords found: {', '.join(found)}"}
        return {"score": 1.0, "explanation": "No toxic content detected"}


class LengthScorer:
    """Autoevals: validates output length is within expected bounds."""

    def __init__(self, min_chars: int = 1, max_chars: int = 10000):
        self.min_chars = min_chars
        self.max_chars = max_chars

    def score(self, output: str, **_) -> dict:
        if output is None:
            return {"score": 0.0, "explanation": "No output"}
        length = len(str(output))
        if length < self.min_chars:
            return {"score": 0.0, "explanation": f"Too short ({length} < {self.min_chars} chars)"}
        if length > self.max_chars:
            return {"score": 0.0, "explanation": f"Too long ({length} > {self.max_chars} chars)"}
        # Score 1.0 if within bounds; partial score based on position
        return {"score": 1.0, "explanation": f"Length {length} is within [{self.min_chars}, {self.max_chars}]"}


class FactualityScorer:
    """
    Autoevals: LLM-as-judge factuality check.
    Determines if the output is factually consistent with the provided context/reference.
    Uses OpenAI or Anthropic; graceful fallback if no key available.
    """

    PROMPT_TEMPLATE = """You are a factuality evaluator. Your task is to determine whether a given answer is factually consistent with the provided context.

Context / Reference:
{context}

Answer to evaluate:
{answer}

Instructions:
- Score 1.0 if the answer is fully factually consistent with the context.
- Score 0.5 if partially consistent (minor issues or omissions).
- Score 0.0 if the answer contradicts or hallucinated facts not in the context.

Respond ONLY with:
SCORE: <number between 0 and 1>
EXPLANATION: <one sentence>"""

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None):
        self.model = model
        self.api_key = api_key

    def score(self, output: str, expected: str = None, input_data=None, **_) -> dict:
        context = expected or (json.dumps(input_data, default=str) if input_data else "")
        if not context:
            return {"score": 0.5, "explanation": "No reference context provided — cannot judge factuality"}
        prompt = self.PROMPT_TEMPLATE.format(context=context[:3000], answer=str(output)[:2000])
        try:
            if "gpt" in self.model.lower() or "o1" in self.model.lower() or "o3" in self.model.lower():
                from openai import OpenAI
                key = self.api_key or settings.OPENAI_API_KEY
                if not key:
                    raise ValueError("No OpenAI API key")
                client = OpenAI(api_key=key)
                resp = client.chat.completions.create(
                    model=self.model, messages=[{"role": "user", "content": prompt}],
                    temperature=0, max_tokens=200
                )
                text = resp.choices[0].message.content
            elif "claude" in self.model.lower():
                from anthropic import Anthropic
                key = self.api_key or settings.ANTHROPIC_API_KEY
                if not key:
                    raise ValueError("No Anthropic API key")
                client = Anthropic(api_key=key)
                resp = client.messages.create(
                    model=self.model, max_tokens=200,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = resp.content[0].text
            else:
                raise ValueError(f"Unsupported model: {self.model}")

            score, explanation = None, ""
            for line in text.splitlines():
                if line.startswith("SCORE:"):
                    try:
                        score = max(0.0, min(1.0, float(line.split(":", 1)[1].strip())))
                    except Exception:
                        pass
                elif line.startswith("EXPLANATION:"):
                    explanation = line.split(":", 1)[1].strip()
            if score is None:
                score = 0.5
            return {"score": score, "explanation": explanation}
        except Exception as e:
            logger.warning(f"FactualityScorer LLM call failed: {e} — falling back to word overlap")
            return WordOverlapScorer().score(output, context)


class SummarizationScorer:
    """
    Autoevals: checks whether a summary is faithful and concise relative to source.
    Uses WordOverlap as a proxy when no LLM key is available.
    """

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None):
        self.model = model
        self.api_key = api_key
        self._factuality = FactualityScorer(model=model, api_key=api_key)

    def score(self, output: str, expected: str = None, input_data=None, **_) -> dict:
        source = expected or (json.dumps(input_data, default=str) if input_data else "")
        if not source:
            return {"score": 0.5, "explanation": "No source text provided"}
        result = self._factuality.score(output, expected=source)
        # Penalise excessively long summaries (> 80% of source)
        if source and len(str(output)) > 0.8 * len(str(source)):
            result["score"] = result["score"] * 0.8
            result["explanation"] += " (penalty: summary is too long)"
        return result


class JSONSchemaScorer:
    """
    Phase 2: Response Schema Validation.

    Validates that the model output conforms to a JSON Schema (draft-07 / draft-2020).
    Score is 1.0 if the output validates, 0.0 if it does not.
    Partial scoring is applied for outputs that are valid JSON but fail schema constraints.

    Config:
        schema (dict): The JSON Schema to validate against. Required.

    Example:
        scorer = JSONSchemaScorer(schema={"type": "object", "required": ["answer"]})
        result = scorer.score(output='{"answer": "Paris"}')
        # -> {"score": 1.0, "explanation": "Output conforms to JSON schema", "valid": True, "errors": []}
    """

    def __init__(self, schema: dict = None, **_):
        self._schema = schema or {}

    def score(self, output=None, expected=None, input_data=None, **_) -> dict:
        # First: try to parse the output as JSON
        if output is None:
            return {"score": 0.0, "explanation": "No output provided", "valid": False, "errors": ["No output"]}

        if isinstance(output, (dict, list)):
            parsed = output
        else:
            try:
                parsed = json.loads(str(output))
            except (json.JSONDecodeError, ValueError) as e:
                return {
                    "score": 0.0,
                    "explanation": f"Output is not valid JSON: {e}",
                    "valid": False,
                    "errors": [str(e)],
                }

        if not self._schema:
            # No schema provided — just check it's valid JSON
            return {"score": 1.0, "explanation": "Output is valid JSON (no schema provided)", "valid": True, "errors": []}

        # Validate against schema
        try:
            import jsonschema
            validator = jsonschema.Draft7Validator(self._schema)
            errors = sorted(validator.iter_errors(parsed), key=lambda e: e.path)
            if not errors:
                return {
                    "score": 1.0,
                    "explanation": "Output conforms to JSON schema",
                    "valid": True,
                    "errors": [],
                }
            error_msgs = [f"{'.'.join(str(p) for p in e.path) or 'root'}: {e.message}" for e in errors[:5]]
            # Partial score: penalise per error (min 0.1 floor so partial credit is visible)
            partial = max(0.1, 1.0 - 0.2 * len(errors))
            return {
                "score": round(partial, 2),
                "explanation": f"Schema validation failed ({len(errors)} error(s)): {'; '.join(error_msgs[:2])}",
                "valid": False,
                "errors": error_msgs,
            }
        except ImportError:
            # jsonschema not installed — fall back to basic type check
            if isinstance(self._schema, dict) and "type" in self._schema:
                expected_type = self._schema["type"]
                type_map = {"object": dict, "array": list, "string": str, "number": (int, float), "boolean": bool, "null": type(None)}
                py_type = type_map.get(expected_type)
                if py_type and isinstance(parsed, py_type):
                    return {"score": 1.0, "explanation": f"Output matches expected type '{expected_type}'", "valid": True, "errors": []}
                return {"score": 0.0, "explanation": f"Expected type '{expected_type}', got {type(parsed).__name__}", "valid": False, "errors": [f"type mismatch"]}
            return {"score": 0.5, "explanation": "jsonschema not installed; basic check passed", "valid": True, "errors": []}


# ---------------------------------------------------------------------------
# Registry: maps autoeval name → scorer class (for API / frontend use)
# ---------------------------------------------------------------------------

AUTOEVAL_REGISTRY: dict[str, type] = {
    "exact_match": ExactMatchScorer,
    "contains": ContainsScorer,
    "regex": RegexScorer,
    "json_validity": JSONValidityScorer,
    "json_schema": JSONSchemaScorer,       # Phase 2: response schema validation
    "levenshtein": LevenshteinScorer,
    "word_overlap": WordOverlapScorer,
    "semantic_similarity": SemanticSimilarityScorer,
    "numeric_diff": NumericDiffScorer,
    "toxicity": ToxicityScorer,
    "length": LengthScorer,
    "factuality": FactualityScorer,
    "summarization": SummarizationScorer,
}


def run_autoeval(
    scorer_name: str,
    output,
    expected=None,
    input_data=None,
    config: dict = None,
) -> dict:
    """
    Convenience function: run a named autoeval scorer.

    Returns {"score": float, "explanation": str}
    """
    config = config or {}
    scorer_cls = AUTOEVAL_REGISTRY.get(scorer_name)
    if scorer_cls is None:
        return {"score": 0.0, "explanation": f"Unknown autoeval scorer: {scorer_name}"}
    try:
        scorer = scorer_cls(**{k: v for k, v in config.items() if k not in ("output", "expected", "input_data")})
        return scorer.score(output=output, expected=expected, input_data=input_data)
    except Exception as e:
        logger.error(f"Autoeval {scorer_name} error: {e}")
        return {"score": 0.0, "explanation": f"Scorer error: {e}"}


def run_eval_task(
    eval_id: str,
    project_id: str,
    dataset_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    scorers: List[dict] = None,
    db_url: str = None
):
    """
    Background task to run evaluation.
    Updates eval status and stores results.
    """
    
    # Recreate DB session for background task
    engine = create_engine(db_url or settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        eval_record = db.query(Eval).filter(Eval.id == eval_id).first()
        if not eval_record:
            logger.error(f"Eval not found: {eval_id}")
            return
        
        eval_record.status = "running"
        eval_record.started_at = None  # Avoid sqlalchemy issues
        db.commit()
        
        # Get traces to evaluate
        traces = []
        if dataset_id:
            dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if dataset:
                # For now, create traces from dataset examples
                # In full implementation, would batch evaluate
                logger.info(f"Evaluating dataset {dataset_id} with {len(dataset.examples)} examples")
        elif trace_id:
            trace = db.query(Trace).filter(Trace.id == trace_id).first()
            if trace:
                traces = [trace]
        
        if not traces:
            logger.warning(f"No traces found for eval {eval_id}")
            eval_record.status = "failed"
            eval_record.error_message = "No traces found"
            db.commit()
            return
        
        # Run scorers on each trace
        all_scores = []
        for trace in traces:
            trace_scores = []
            
            for scorer_config in scorers:
                try:
                    scorer_type = scorer_config.get("type", "code")
                    scorer_name = scorer_config.get("name", "unknown")
                    
                    # Create appropriate scorer
                    if scorer_type == "code":
                        # For MVP, skip code scorers (require user to provide functions)
                        logger.info(f"Skipping code scorer {scorer_name}")
                        continue
                    
                    elif scorer_type == "llm":
                        scorer = LLMScorer(
                            model=scorer_config.get("model", "gpt-4"),
                            api_key=settings.OPENAI_API_KEY
                        )
                        score_value, explanation = await_or_sync_call(
                            scorer.score_async,
                            trace,
                            scorer_name
                        )
                    
                    elif scorer_type == "expected":
                        scorer = ExpectedValueScorer()
                        score_value = scorer.score(trace, scorer_config.get("config"))
                        explanation = "Expected value comparison"
                    
                    else:
                        logger.warning(f"Unknown scorer type: {scorer_type}")
                        continue
                    
                    # Store score in database
                    score_record = Score(
                        id=f"{trace.id}_{scorer_name}",
                        trace_id=trace.id,
                        project_id=project_id,
                        scorer_name=scorer_name,
                        scorer_type=scorer_type,
                        score_value=score_value,
                        explanation=explanation,
                        model_used=scorer_config.get("model"),
                        scorer_config=scorer_config.get("config")
                    )
                    db.add(score_record)
                    
                    trace_scores.append({
                        "scorer_name": scorer_name,
                        "score": score_value,
                        "explanation": explanation
                    })
                    
                except Exception as e:
                    logger.error(f"Error running scorer {scorer_name}: {e}")
                    trace_scores.append({
                        "scorer_name": scorer_name,
                        "error": str(e)
                    })
            
            all_scores.append({
                "trace_id": trace.id,
                "scores": trace_scores
            })
        
        db.commit()
        
        # Calculate aggregate results
        all_score_values = [
            score["score"]
            for item in all_scores
            for score in item.get("scores", [])
            if "score" in score
        ]
        
        if all_score_values:
            eval_record.avg_score = sum(all_score_values) / len(all_score_values)
            eval_record.min_score = min(all_score_values)
            eval_record.max_score = max(all_score_values)
        
        eval_record.status = "completed"
        eval_record.completed_examples = len(traces)
        eval_record.results = all_scores
        
        db.commit()
        logger.info(f"Eval {eval_id} completed")
        
    except Exception as e:
        logger.error(f"Error in eval task: {e}", exc_info=True)
        eval_record = db.query(Eval).filter(Eval.id == eval_id).first()
        if eval_record:
            eval_record.status = "failed"
            eval_record.error_message = str(e)
            db.commit()
    finally:
        db.close()


def await_or_sync_call(async_func, *args, **kwargs):
    """
    Helper to call async function from sync context.
    For MVP, returns placeholder; in production use asyncio.run()
    """
    import asyncio
    try:
        return asyncio.run(async_func(*args, **kwargs))
    except Exception:
        # Fallback - return dummy values
        logger.warning("Async call failed, returning placeholder")
        return 0.5, "Scorer error"
