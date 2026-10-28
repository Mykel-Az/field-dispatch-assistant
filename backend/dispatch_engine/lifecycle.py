"""Job lifecycle rules. Pure: no Django, no DB, satisfies lint-imports."""

# 1. Explicit String Constants for models.py mapping
UNASSIGNED = "unassigned"
ASSIGNED = "assigned"
ONGOING = "ongoing"
INCOMPLETE = "incomplete"
COMPLETED = "completed"
FAILED = "failed"
CANCELED = "canceled"

# 2. Immutable Transition Definition Maps
TRANSITIONS: dict[str, frozenset[str]] = {
    UNASSIGNED: frozenset({ASSIGNED, CANCELED}),
    ASSIGNED: frozenset({UNASSIGNED, ONGOING, CANCELED}),
    ONGOING: frozenset({COMPLETED, INCOMPLETE, FAILED}),
    INCOMPLETE: frozenset({UNASSIGNED}),
    COMPLETED: frozenset(),
    FAILED: frozenset(),
    CANCELED: frozenset(),
}

TERMINAL = frozenset(
    state for state, next_states in TRANSITIONS.items() if not next_states
)
REASON_REQUIRED = frozenset({INCOMPLETE, FAILED, CANCELED})


# 3. Custom Structural Exceptions
class IllegalTransition(Exception):
    """Raised when a status shift violates the lifecycle matrix rules."""

    def __init__(self, src: str, dst: str):
        super().__init__(
            f"Illegal state transition sequence: '{src}' cannot move to '{dst}'."
        )
        self.src, self.dst = src, dst


# 4. Engine Utilities & Validation Engine (The Best of Version 1)
class JobLifecycleEngine:
    """Combines Version 1's validation/printing with Version 2's immutability."""

    @staticmethod
    def get_next_states(current_state: str) -> frozenset[str]:
        """Returns the set of next valid states from the current state."""
        return TRANSITIONS.get(current_state, frozenset())

    @staticmethod
    def is_terminal(state: str) -> bool:
        """Checks if a state has no further outbound transitions."""
        return state in TERMINAL

    @staticmethod
    def can_transition(src: str, dst: str) -> bool:
        """Boolean check for evaluating state movements."""
        return dst in TRANSITIONS.get(src, frozenset())

    @staticmethod
    def check_transition(src: str, dst: str) -> None:
        """Enforces a hard state rule change or raises an Exception."""
        if not JobLifecycleEngine.can_transition(src, dst):
            raise IllegalTransition(src, dst)

    @classmethod
    def print_transition_table(cls):
        """Generates a scannable text-based transition table for documentation."""
        all_states = sorted(TRANSITIONS.keys())
        print(f"\n{'Current State':<15} | {'Valid Next States':<35} | Status")
        print("-" * 70)
        for state in all_states:
            next_states = TRANSITIONS.get(state, frozenset())
            next_states_str = (
                f"{{{', '.join(sorted(next_states))}}}" if next_states else "{}"
            )
            status = "Terminal" if cls.is_terminal(state) else "Active"
            print(f"{state:<15} | {next_states_str:<35} | {status}")


if __name__ == "__main__":
    print("--- TASK LIFECYCLE TRANSITION TABLE ---")
    JobLifecycleEngine.print_transition_table()
