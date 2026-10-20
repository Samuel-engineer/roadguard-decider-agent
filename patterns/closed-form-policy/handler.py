"""Declared Strands Policy pattern — API-agnostic core + thin Strands adapter.

Two layers live here, deliberately split so the unverified Strands surface is
quarantined:

1. ``evaluate_policy`` / ``PolicyOutcome`` — a pure, framework-free core. It
   turns the ``(facts, references)`` of a scene into a closed-form
   classification by calling the SAME ``decide(...)`` used in production. It
   never imports ``strands`` and never talks to AWS directly (the Decider
   client is injected).

2. ``ClosedFormPolicyHandler`` — a THIN adapter over ``strands`` confirmed
   against strands-agents 1.61.1 (see FEAT-003 findings). It subclasses
   ``strands.interventions.InterventionHandler`` and overrides
   ``before_tool_call`` (the exact hook name/signature confirmed from the
   installed version). It maps a ``PolicyOutcome`` onto the installed action
   objects (``Proceed`` / ``Deny``) from ``strands.interventions``. If the
   Strands API shifts, only this class changes — ``evaluate_policy`` and
   ``decide`` are untouched.

The two variants ("choice" for the driving-exam QCM, "noul" for the free-form
driving situation) share this one handler; they differ only by the ``mode``
passed through to ``decide``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Mode names understood by the shared ``decide``: the exam circuit emits
# multiple-choice ("choice") questions; the situation circuit emits one
# yes/no ("noul") question per candidate driver intention.
_VARIANT_TO_MODE = {
    "choice": "exam",
    "noul": "situation",
}


@dataclass
class PolicyOutcome:
    """Framework-free result of one closed-form policy evaluation.

    ``allow`` is a coarse verdict used by the Strands adapter to pick an action
    object; ``cards`` carries the full closed-form classification (one card per
    question / intention) exactly as the production response projects it.
    """

    allow: bool
    reason: str
    cards: list[dict[str, Any]] = field(default_factory=list)
    decision: Any = None


def _build_cards(mode: str, facts: dict[str, Any], decision: Any) -> list[dict[str, Any]]:
    """Project the Decider ``decision`` into closed-form cards.

    Reuses the production ``build_response`` projection when it is importable
    (keeping cards byte-identical to the API); falls back to a minimal local
    projection otherwise so the pattern stays usable standalone.
    """
    try:
        from functions.core.circuits.present import build_response
    except ImportError:
        return _fallback_cards(mode, facts, decision)
    response = build_response(mode, facts, [], decision, media_key="", elapsed_ms=0)
    return response.get("cards", [])


def _fallback_cards(mode: str, facts: dict[str, Any], decision: Any) -> list[dict[str, Any]]:
    answers = decision.get("answers", {}) if isinstance(decision, dict) else {}
    cards: list[dict[str, Any]] = []
    intentions = facts.get("intentions", []) or []
    for index, intention in enumerate(intentions, start=1):
        answer = answers.get(str(index), {})
        selected = answer.get("selected_options") or []
        cards.append(
            {
                "id": str(index),
                "title": intention,
                "kind": "allow_deny",
                "options": [
                    {"label": "Autorisé", "selected": "Autorisé" in selected},
                    {"label": "Interdit", "selected": "Interdit" in selected},
                ],
            }
        )
    return cards


def evaluate_policy(
    facts: dict[str, Any],
    references: list[dict[str, Any]],
    runtime: Any,
    *,
    mode: str,
    decide: Callable[..., tuple[Any, int]],
    request_id: str | None = None,
) -> PolicyOutcome:
    """Run the shared Decider policy over a perceived scene.

    This is the API-agnostic core. ``decide`` is injected (so no AWS client is
    pulled at import time) and is exactly the production ``decide`` — the
    pattern and the Lambda classify through the same code path. ``mode`` is the
    circuit mode ("exam" or "situation"); it is passed straight to ``decide``.
    """
    decision, _elapsed_ms = decide(
        facts,
        references,
        runtime,
        request_id=request_id,
        mode=mode,
    )
    cards = _build_cards(mode, facts, decision)
    allow = any(
        option.get("selected") and option.get("label") in {"Autorisé", "Oui"}
        for card in cards
        for option in card.get("options", [])
    )
    reason = (
        "Au moins une intention est conforme au Code de la route."
        if allow
        else "Aucune intention conforme au Code de la route n'a été retenue."
    )
    return PolicyOutcome(allow=allow, reason=reason, cards=cards, decision=decision)


try:  # pragma: no cover - import guarded so the core stays usable without strands
    from strands.interventions import Deny, InterventionHandler, Proceed

    _STRANDS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _STRANDS_AVAILABLE = False
    InterventionHandler = object  # type: ignore[assignment,misc]


class ClosedFormPolicyHandler(InterventionHandler):  # type: ignore[misc,valid-type]
    """Thin Strands adapter wiring the closed-form policy into an agent.

    Confirmed against strands-agents 1.61.1: ``InterventionHandler`` is an ABC
    that requires a ``name`` property and lets subclasses override lifecycle
    methods at class level. We override ``before_tool_call(self, event, **kwargs)``;
    it returns one of the ``strands.interventions`` action objects
    (``Proceed`` / ``Deny``). We read the tool input from
    ``event.tool_use['input']`` and classify it with ``evaluate_policy`` before
    the tool runs. The latest outcome is stashed on ``last_outcome`` for the
    caller to read cards/decision.
    """

    def __init__(
        self,
        *,
        variant: str,
        decide: Callable[..., tuple[Any, int]],
        runtime: Any = None,
        references: list[dict[str, Any]] | None = None,
    ) -> None:
        if not _STRANDS_AVAILABLE:
            raise RuntimeError(
                "strands-agents n'est pas installé : ClosedFormPolicyHandler "
                "nécessite le paquet strands (groupe dev uniquement)."
            )
        if variant not in _VARIANT_TO_MODE:
            raise ValueError(
                f"Variante inconnue : {variant!r}. Utilisez 'choice' ou 'noul'."
            )
        self.variant = variant
        self.mode = _VARIANT_TO_MODE[variant]
        self._decide = decide
        self._runtime = runtime
        self._references = references or []
        self.last_outcome: PolicyOutcome | None = None

    @property
    def name(self) -> str:
        return f"closed-form-policy:{self.variant}"

    def evaluate(self, facts: dict[str, Any]) -> PolicyOutcome:
        """Classify a perceived scene without going through Strands."""
        outcome = evaluate_policy(
            facts,
            self._references,
            self._runtime,
            mode=self.mode,
            decide=self._decide,
        )
        self.last_outcome = outcome
        return outcome

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        """Classify the scene carried by the tool call, then allow or deny."""
        tool_input = {}
        try:
            tool_input = event.tool_use.get("input", {}) or {}
        except AttributeError:
            tool_input = {}
        facts = tool_input.get("facts", tool_input)
        if not isinstance(facts, dict):
            return Proceed()
        outcome = self.evaluate(facts)
        if outcome.allow:
            return Proceed(reason=outcome.reason)
        return Deny(reason=outcome.reason)
