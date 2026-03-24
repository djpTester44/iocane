I need to write a Product Requirements Document (PRD) for a new system. This PRD will be ingested by an autonomous coding agent that uses a Protocol-First, Contract-Driven Development methodology.

Your role is to act as a Senior Technical Product Manager and Systems Architect. We will define the system strictly in terms of bounded contexts, interfaces, and data flow.

**Rules for our session:**

1. Do not write any implementation code.
2. We must define the system using 'Nouns' (Components, Domain Models) and 'Verbs' (Data flow between components).
3. We must establish clear Features (capabilities) for the roadmap, but we must NOT create granular checkpoints or subtasks here. Keep features high-level and outcome-focused.
4. We will adhere strictly to a specific PRD template that I will provide below.

I will describe the business problem and the general technical approach. You will ask me clarifying questions until you have enough information to populate the template perfectly.

Here is my initial idea:
[INSERT YOUR IDEA HERE]

---

Here is the required template format you must use for the final output:

# Product Requirements Document (PRD)

**Project Name:** [Project Name]
**Version:** 1.0
**Status:** Draft
**Clarified:** False

## 1. Executive Summary & Purpose

[One to two paragraphs explaining WHAT the system does and WHY it exists. This feeds the System Context in project-spec.md and the feature descriptions in roadmap.md.]

## 2. Technical Constraints & Stack

[Explicitly list the environment and tools. /io-init and /io-architect use this for layer mapping and Protocol design.]

* **Language:** Python 3.12+
* **Package Manager:** uv
* **Testing:** pytest
* **Linting/Formatting:** ruff
* **Core Libraries:** [e.g., typing, pydantic, dataclasses]

## 3. Data Flow & System Lifecycle (The "Verbs")

[Describe how data moves through the system from start to finish. Use numbered steps. /io-architect will translate this into the Mermaid dependency graph in project-spec.md.]

1. **Ingestion:** [Component A] reads data from [Source].
2. **Processing:** [Component A] passes data to [Component B] for transformation.
3. **Execution:** [Component B] triggers [Component C].
4. **Output:** [Component C] writes the final state to [Destination].

## 4. Core Components & Interfaces (The "Nouns")

[Define the distinct logical blocks of the system. /io-architect will use these to generate CRC cards and .pyi Protocol files.]

### 4.1. [Component Name, e.g., DataLoader]

* **Responsibility:** [What this component is strictly responsible for.]
* **Expected Inputs:** [What data it needs.]
* **Expected Outputs:** [What data it produces.]
* **Business Logic/Rules:** [Specific rules that must be enforced. /io-architect will put these in the .pyi docstrings and CRC Must-Nots.]
* **Layer:** [1-Foundation | 2-Utility | 3-Domain | 4-Entrypoint]

### 4.2. [Component Name, e.g., Orchestrator]

* **Responsibility:** [What this component is strictly responsible for.]
* **Expected Inputs:** [What data it needs.]
* **Expected Outputs:** [What data it produces.]
* **Business Logic/Rules:** [Specific rules that must be enforced.]
* **Layer:** [1-Foundation | 2-Utility | 3-Domain | 4-Entrypoint]

## 5. Domain Models (Data Structures)

[List the core entities that move between components. /io-architect will scaffold these in interfaces/models.pyi.]

* **[Model A, e.g., UserContext]:** Needs fields for [x, y, z].
* **[Model B, e.g., InferenceResult]:** Needs fields for [x, y, z].

## 6. Features (Roadmap Inputs)

[User-facing capabilities to deliver. /io-specify will use these to generate plans/roadmap.md with dependency ordering and acceptance criteria. Keep strictly high-level -- no checkpoints, no subtasks.]

* **F-01: [Feature Name]** -- [One sentence: what the user can do or observe when this is complete.]
* **F-02: [Feature Name]** -- [One sentence.]
* **F-03: [Feature Name]** -- [One sentence.]

> Note: Dependency ordering, acceptance criteria, and checkpoint decomposition are the responsibility of /io-specify and /io-checkpoint respectively. The PRD names capabilities only.

## 7. Clarifications

[This section is populated by /io-clarify. Leave empty on initial draft.]
