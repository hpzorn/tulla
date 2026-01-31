# TODO: Add Peircean Abduction Mode to Epistemology-Ralph

## Context
User requested adding abduction (Peirce) support to epi-ralph. Session interrupted for MCP restart.

## Peirce's Abduction

Abduction is "inference to the best explanation":

```
Surprising fact:     C is observed
Rule:                If A, then C would be expected
Abductive inference: Therefore, A is probably true
```

## Proposed Implementation

### New Mode Flag
```bash
./epistemology-ralph.sh --phenomenon "Surprising observation to explain"
# or
./epistemology-ralph.sh --abduction "Surprising observation to explain"
```

### Mode Logic

1. **Input**: A surprising observation/phenomenon
2. **Search**: Find potential explanatory theories in:
   - Idea pool (semantic search)
   - Web (recent research)
3. **Generate Hypotheses**: Ranked by:
   - **Explanatory power**: How well does it explain the observation?
   - **Prior plausibility**: How likely was this before observing?
   - **Testability**: How could we verify/falsify this hypothesis?
   - **Simplicity**: Occam's razor

### Output Format

```markdown
# Abductive Analysis: [Phenomenon]

## Surprising Observation
[The phenomenon to explain]

## Hypothesis 1: [Title]
**Explanation**: How this accounts for the observation
**Prior Plausibility**: High/Medium/Low
**Testability**: How to verify/falsify
**Explanatory Power**: How much of the observation it covers

## Hypothesis 2: ...

## Recommended Investigation
[Which hypothesis to test first and how]
```

### Metadata for Saved Ideas
```yaml
author: AI
source: epi-ralph
mode: abduction
phenomenon: [the observation]
protocol: peircean-abduction
```

## File to Modify
`/Users/sandboxuser/ideasralph/epistemology-ralph.sh`

Add new function `run_abduction_mode()` around line 410 (after signal mode).

## Resume Command
After MCP restart:
```
Add Peircean abduction mode to epistemology-ralph.sh per TODO-abduction-mode.md
```
