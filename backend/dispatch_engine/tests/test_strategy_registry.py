from api.models import Organization
from dispatch_engine.scoring import STRATEGIES


def test_the_engine_strategies_match_the_organization_choices():
    """If one side gains a strategy and the other does not, a saved choice would crash planning."""
    assert {value for value, _ in Organization.ScoringStrategy.choices} == set(
        STRATEGIES
    )
