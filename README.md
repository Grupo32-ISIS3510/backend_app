# Second Serving

---

## Development Workflow

### 📅 Project Hierarchy

Each Sprint acts as a milestone and contains a flexible number of **MicroSprints (MS)** for iterative delivery.

* **Sprint 1 - 4:** High-level project phases/milestones.
* **MicroSprints (MS):** Weekly execution cycles within a Sprint.

---

### 🏷️ Issue Naming Convention

All issue titles must follow the standard pattern:  
`[SCOPE][S-X][MS-Y] Brief descriptive title`

#### 1. Scope Prefixes (`[SCOPE]`)
| Prefix | Name | Description |
| :--- | :--- | :--- |
| **`[IND]`** | Individual | Tasks assigned to and executed by a single owner. |
| **`[GRP]`** | Group | Collaborative efforts (Pair programming, brainstorming, meetings). |

#### 2. Sprint & MicroSprint Tracking
* **`[S-X]`**: The Main Sprint number (1 to 4).
* **`[MS-Y]`**: The MicroSprint number within that specific phase.

#### 💡 Examples
* `[IND][S-1][MS-2] Put sticky notes with your ideas about how to solve the problem`
* `[GRP][S-2][MS-1] Discuss all the ideas about how to solve the problem`
* `[IND][S-3][MS-4] Vote for your favorite ideas`

---

### 🚦 Workflow & Statuses

We utilize the **GitHub Project Board** with the following pipeline:

1. **Todo:** Refined tasks ready to be started.
2. **In Progress:** Tasks currently under development.
3. **In Review:** Pull Requests (PRs) or tasks awaiting peer feedback/QA.
4. **Done:** Successfully tested and merged into the main branch.

---

### 📝 Issue Structure Requirement

When creating an issue, please ensure it meets the **Definition of Ready (DoR)**:

#### 🎯 Context
Brief explanation of the "Why" and the user value.

#### 🛠️ Technical Implementation
List of systems involved (e.g., Twilio Studio, Intercom API, Azure Functions).

### ✅ Checklist (Definition of Done)
- [ ] Task A
- [ ] Task B
- [ ] Unit testing/Manual validation

### 🚩 Acceptance Criteria
- Must handle [X] condition.
- Must return [Y] response.
