class TaskLifecycleModel:
    def __init__(self, transitions: dict[str, set[str]], terminal_states: set[str]):
        self.transitions: dict[str, set[str]] = transitions
        self.terminal_states: set[str] = terminal_states

    def get_next_states(self, current_state: str) -> set[str]:
        """Returns the set of next valid states from the current state."""
        return self.transitions.get(current_state, set())

    def is_terminal(self, state: str) -> bool:
        """Checks if a state has no further transitions."""
        return state in self.terminal_states

    def print_transition_table(self):
        """Prints a scannable text-based transition table."""
        # Get all unique states to display comprehensive rows
        all_states = sorted(list(self.transitions.keys()) + list(self.terminal_states))

        print(f"{'Current State':<15} | {'Valid Next States':<30} | Status")
        print("-" * 60)

        for state in all_states:
            next_states = self.transitions.get(state, set())

            # Format the next states set nicely
            if next_states:
                next_states_str = f"{{{', '.join(sorted(next_states))}}}"
            else:
                next_states_str = "{}"

            status = "Terminal" if self.is_terminal(state) else "Active"
            print(f"{state:<15} | {next_states_str:<30} | {status}")


# --- Initialize the Model with Your Rules ---
if __name__ == "__main__":
    # The transition configuration adhering strictly to dict[str, set[str]]
    lifecycle_transitions: dict[str, set[str]] = {
        "unassigned": {"assigned", "canceled"},
        "assigned": {"unassigned", "ongoing", "canceled"},
        "ongoing": {"completed", "incomplete", "failed"},
        "incomplete": {"unassigned"},  # Back to queue
    }

    # Explicitly tracking terminal states (they map to an empty set automatically)
    terminal_states: set[str] = {"completed", "failed", "canceled"}

    # Create the model instance
    model = TaskLifecycleModel(lifecycle_transitions, terminal_states)

    # Print the resulting lifecycle table
    print("--- TASK LIFECYCLE TRANSITION TABLE ---")
    model.print_transition_table()

    # Example Validation check
    print("\n--- STATE CHECK EXAMPLES ---")
    print(
        f"Can 'ongoing' transition to 'completed'? {'completed' in model.get_next_states('ongoing')}"
    )
    print(f"Is 'failed' a terminal state? {model.is_terminal('failed')}")
