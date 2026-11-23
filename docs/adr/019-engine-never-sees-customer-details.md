# ADR-019: The planning engine never sees customer details

Date: 2026-11-23 · Status: Accepted · Written after the fact: the rule has been
enforced by the adapter and a test since the engine was built (S2-4), and
earlier ADRs and code comments already cite it.

## Context
The engine plans a day from where jobs are, when they must start, how long they
take and what skills they need. It does not need to know *who* the customer is.
Meanwhile the places that handle engine data are the least controlled ones: debug
logs on a hosted service, test failures printed in CI, Hypothesis counterexamples,
and, in the Sprint 3 stretch, wording explanations with an AI model, which would
send text to an outside provider. A customer's name, phone number and street
address are personal data of people who never agreed to any of that.

## Decision
1. `api/adapters.py` is the only place that builds engine inputs, and it copies
   only what planning needs. `JobView` carries the job's id, **title** (as its
   label), coordinates, urgency, priority, slot, duration and skill ids.
   `TechView` carries ids, skill ids, shift times, availability, position and
   load. `Job.customer_name`, `customer_phone`, the street address and the
   free-text description are never copied.
2. The engine's types have no field for them, so a later change cannot pass them
   along by accident; it would have to add a field, in review.
3. Engine logs (`dispatch_engine.assign`) and the planner trace in
   `api/services/scheduling` write ids and numbers only: no labels, no names.
4. Explanations are built from structured reasons (codes with numbers). The
   sentence uses the job title and the technician's name, and is shown only
   inside the same organization (ADR-016). Any future AI wording takes the
   structured reasons, not the stored sentence, and the same rule applies to it.
5. A test (`test_the_engine_never_sees_customer_details`) builds a job with a
   known name, phone and address and asserts none appears in the engine view.

## Alternatives considered
- **Pass the whole Job and trust the engine to ignore it**: easy, but every log
  line and every future caller then holds personal data, and the engine would
  have to import Django to read it (ADR-008).
- **Remove the title too**: stricter, but the title is what makes an
  explanation readable ("Rooftop unit swap"), and it is staff-facing text.

## Trade-offs
- The title is free text: it defaults to the first line of the problem
  description and the dispatcher can edit it. If someone writes a customer's name
  or address on that first line, the engine's label and the explanation sentence
  carry it (the sentence is stored on the job and shown inside the organization).
  The rule protects the fields that are meant to hold customer details; it cannot
  police what staff write in a description. Logs stay safe either way (point 3).
  A hint under the title field would help; not built.
- A technician's label is their name, or their email if they have no name. That
  is staff data, not customer data, and stays inside the organization.
- Anything new the engine needs (for example a customer's access hours) must be
  added to the types on purpose, with a reason, not read off the model.
