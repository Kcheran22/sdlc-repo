PARSE_REQUIREMENTS_PROMPT = """
You are a senior Business Analyst specialising in SDLC documentation.

Analyse the BRD and FRD documents below and extract every distinct requirement.
Merge duplicates; resolve contradictions in favour of the FRD.

── BRD ──────────────────────────────────────────────────────────────────────
{brd_content}

── FRD ──────────────────────────────────────────────────────────────────────
{frd_content}

Return ONLY a valid JSON object (no markdown fences, no commentary):
{{
  "requirements": [
    {{
      "id": "REQ-001",
      "type": "functional | non-functional",
      "source": "BRD | FRD | Both",
      "category": "<logical grouping e.g. Authentication, Reporting>",
      "description": "<clear, concise requirement statement>",
      "priority": "High | Medium | Low"
    }}
  ]
}}
"""

GROUP_INTO_EPICS_PROMPT = """
You are an experienced Agile Product Owner.

Group the following requirements into logical epics. Each epic should represent
a coherent business capability or feature cluster. Aim for 3–8 epics.

── Requirements ─────────────────────────────────────────────────────────────
{requirements}

Return ONLY a valid JSON object:
{{
  "epics": [
    {{
      "id": "EPIC-001",
      "title": "<short, meaningful title>",
      "description": "<1–2 sentence description of the business capability>",
      "business_value": "<why this matters to the business>",
      "priority": "High | Medium | Low",
      "source_requirements": ["REQ-001", "REQ-002"]
    }}
  ]
}}
"""

GENERATE_STORIES_PROMPT = """
You are an Agile Coach helping a team decompose an epic into user stories.

── Epic ─────────────────────────────────────────────────────────────────────
{epic}

── Related Requirements ─────────────────────────────────────────────────────
{requirements}

Generate 3–6 well-scoped user stories for this epic.
Use the "As a <role>, I want <goal>, so that <benefit>" format.

Return ONLY valid JSON:
{{
  "stories": [
    {{
      "id": "{epic_id}-STORY-01",
      "epic_id": "{epic_id}",
      "title": "<short title>",
      "user_story": "As a <role>, I want <goal>, so that <benefit>.",
      "description": "<additional detail, constraints, or clarifications>",
      "priority": "High | Medium | Low",
      "story_points": <Fibonacci: 1 | 2 | 3 | 5 | 8 | 13>,
      "complexity": "Simple | Medium | Complex"
    }}
  ]
}}
"""

GENERATE_AC_PROMPT = """
You are a QA Lead writing acceptance criteria for a development team.

── User Story ───────────────────────────────────────────────────────────────
{story}

── Epic Context ─────────────────────────────────────────────────────────────
{epic}

Write 3–5 acceptance criteria in Given / When / Then format, plus a Definition of Done checklist.

Return ONLY valid JSON:
{{
  "acceptance_criteria": [
    {{
      "id": "AC-01",
      "scenario": "<scenario name>",
      "given": "<precondition>",
      "when": "<action taken>",
      "then": "<expected observable outcome>"
    }}
  ],
  "definition_of_done": [
    "<item 1>",
    "<item 2>"
  ]
}}
"""

ASSIGN_OWNER_PROMPT = """
You are an AI Automation Architect deciding who executes each user story.

Decision rules
──────────────
• "Agent"  → highly repetitive, rule-based, data generation, code scaffolding — low human judgement needed
• "Human"  → stakeholder negotiation, complex UX, security-sensitive, regulatory sign-off
• "Hybrid" → automatable core with human review / approval gate

── Task Assignment Config ───────────────────────────────────────────────────
{task_assignment}

── Stories ──────────────────────────────────────────────────────────────────
{stories}

Return ONLY valid JSON:
{{
  "assignments": [
    {{
      "story_id": "<story id>",
      "execution_owner": "Human | Agent | Hybrid",
      "executor_role": "<Developer | QA Engineer | DevOps Engineer | AI Agent | Business Analyst>",
      "rationale": "<1–2 sentence justification>",
      "automation_percentage": <0–100>
    }}
  ]
}}
"""
