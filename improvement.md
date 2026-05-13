# Improvement Log for `docs/project.tex`

This file records ten strict review-and-revision passes, written from the viewpoint of a demanding instructor/TA reading the project statement and the generated PDF.

## Round 1

**Criticism.** Problem 2 in the report incorrectly spends space describing the heuristic. The project statement says Problem 2 is the code submission task, while Problem 3 is where the heuristic should be introduced in words.

**Revision target.** Make Problem 2 short: state that the deliverable is the Python function returning `assignment` and `relocation`, and move all algorithmic explanation to Problem 3.

## Round 2

**Criticism.** The report uses internal names such as Algo1 and Algo5. This sounds like an implementation diary rather than a polished algorithm description.

**Revision target.** Rename them as two pre-build approaches: Approach A, revenue-first route insertion; Approach B, demand-aware look-ahead construction. Internal filenames may be avoided.

## Round 3

**Criticism.** The three-minute execution limit is not emphasized enough as the central design constraint.

**Revision target.** Start Problem 3 by saying the algorithm is deliberately split into a fast pre-build stage and a time-limited optimization stage because each hidden instance must finish within three minutes.

## Round 4

**Criticism.** Approach A is under-described. A reader cannot see exactly how route insertion respects timing, relocation budget, and free upgrade constraints.

**Revision target.** Explain sorting by revenue, checking level compatibility, binary-searching chronological insertion position, testing predecessor/successor feasibility, computing incremental moving time, and tie-breaking.

## Round 5

**Criticism.** Approach B is under-described. It should mention the scoring formula and why the term `3R` appears.

**Revision target.** Explain that accepting order `k` improves profit by `3R_k` relative to rejecting it, since total profit equals `3 * accepted revenue - 2 * total revenue`. Explain future station score, opportunity cost, move penalty, idle penalty, and upgrade penalty.

## Round 6

**Criticism.** The Approach B repair phases are too vague. The implementation has concrete phases that should be summarized.

**Revision target.** Add shortage-bucket rescue, route insertion, one-removal swap, last-order replacement, and small-instance exact DFS fallback.

## Round 7

**Criticism.** Batch IP optimization is described but not convincingly enough. It should show why it is powerful and still fast.

**Revision target.** Describe route conversion, sampling low-efficiency routes, releasing only selected cars, selecting candidate orders, solving a local network-flow IP, and accepting only improving repairs.

## Round 8

**Criticism.** Time complexity should be split by stage. A single rough complexity expression is not enough for a 25-point Problem 3.

**Revision target.** Provide separate complexity for Approach A, Approach B, and local IP repair. State the local IP has `O(bm^2)` arcs/variables/constraints with capped `b` and `m`, and total runtime is wall-clock bounded.

## Round 9

**Criticism.** Problem 4 does not fully satisfy the instruction "clearly indicate how the instances are generated." It lists scenarios but not enough fixed values and distributions.

**Revision target.** Add `n_S`, `n_L`, `n_D`, `n_C`, `n_K`, rates, station distributions, level distributions, time distributions, and budget rules from `generate_code.py`.

## Round 10

**Criticism.** Problem 4 should explicitly connect benchmarks to upper/lower bounds and include the histogram figure in the report.

**Revision target.** State that the exact IP optimum is the upper/optimal benchmark on the selected solvable instance range, while the chronological minimum-moving-time heuristic is a feasible lower-bound baseline. Include the combined histogram figure and interpret the mean/std results.

---

# Formal Ten-Pass Revision

## Pass 1

**Strict criticism.** Problem 2 must not look like a second algorithm-description section. The current version is short, but it still says "reported in Problem 3" without explicitly acknowledging the required grading interface.

**Correction applied.** Tighten Problem 2 around the function interface and feasibility requirements, and keep all design rationale in Problem 3.

## Pass 2

**Strict criticism.** Approach A is called a "baseline" inside Problem 3. This is confusing because Problem 4 already uses a different simple baseline. The two pre-build methods should sound like peer approaches from our team, not one official method and one benchmark.

**Correction applied.** Rename the description of Approach A from "baseline" to "incumbent generator" and keep both pre-build methods as equal design components.

## Pass 3

**Strict criticism.** The three-minute limit is mentioned, but the report does not explicitly explain how the time is budgeted between construction and improvement. A grader could ask why batch IP will not overrun.

**Correction applied.** Add a time-budget sentence: pre-build obtains the incumbent in seconds, while the improvement loop is governed by the remaining wall-clock time and short local IP limits.

## Pass 4

**Strict criticism.** Approach A says "additional moving time" but does not define it. For a route-insertion heuristic, this is a central feasibility and objective-preservation detail.

**Correction applied.** Add the explicit marginal moving-time expression for inserting order `k` between predecessor `i` and successor `j`.

## Pass 5

**Strict criticism.** Approach B still looks like a black-box score. The future demand table should be explained from the code: six-hour buckets and a rolling 24-hour look-ahead.

**Correction applied.** Add how demand values are accumulated into station-level and car-level buckets, including upgrade-compatible demand and rolling look-ahead windows.

## Pass 6

**Strict criticism.** The repair phases are listed, but not enough is said about why they remain feasible. A strict grader may suspect that these repairs can break timing or relocation-budget constraints.

**Correction applied.** Add that every repaired route is simulated from the car's initial station and readiness time, and is accepted only after checking timing, level compatibility, and total moving time.

## Pass 7

**Strict criticism.** The batch IP repair says "candidate orders" but not how they are selected. This matters because the local IP quality depends on not wasting variables on irrelevant orders.

**Correction applied.** Clarify that released orders are prioritized, then compatible currently rejected/high-revenue orders are added up to a candidate limit.

## Pass 8

**Strict criticism.** Complexity still omits the number of local repair iterations. A grader could ask whether many small IPs can still become too expensive.

**Correction applied.** Add a wall-clock bound: if each local IP receives at most `tau` seconds, the number of iterations is at most approximately `T/tau`, plus candidate-building overhead.

## Pass 9

**Strict criticism.** The experiment section still omits some exact generator distributions: rate generation, pickup-time range, and rental duration. The project statement explicitly asks for fixed values and probability distributions.

**Correction applied.** Add the rate process, pickup-time generation, peak/weekend distribution, and 2-to-48-hour rental duration used by `generate_code.py`.

## Pass 10

**Strict criticism.** The final interpretation is strong, but it does not explicitly say where the detailed evidence is stored, and it should connect mean/std and histograms more directly to the project requirement.

**Correction applied.** Add a final sentence tying the table, histogram, and compressed raw artifact together as reproducibility evidence.

## Additional user-directed pass

**Strict criticism.** The formal ten-pass draft was derived mainly from code and still did not use the two curated description files. The user explicitly requested using `docs/algo1_description.md` for Algorithm A and `docs/algo5_description.md` for Algorithm B.

**Correction applied.** Rewrote the Algorithm A subsection around the four documented steps: order prioritization, chronological insertion search, feasibility evaluation, and lexicographical selection. Rewrote the Algorithm B subsection around the five documented phases: initial greedy assignment, shortage-bucket repair, limited route insertion, one-removal swaps, and limited local replacement, while retaining the score formula and complexity analysis.
