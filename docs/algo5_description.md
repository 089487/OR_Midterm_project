Approach B is executed through a series of sequential phases to construct and iteratively improve the assigned routes:

\begin{itemize}
    \item \textbf{Phase 1: Initial Greedy Assignment.} Orders are sorted based on parameter variants (e.g., bucketed density, chronological) and greedily assigned to cars using the evaluation score.
    \item \textbf{Phase 2: Shortage-bucket Repair.} A rescue phase for rejected high-value orders, focusing on stations and time buckets with concentrated demand and low expected relocation effort.
    \item \textbf{Phase 3: Limited Route-insertion.} Evaluates the direct insertion of rejected high-value orders into existing car routes without causing infeasibility.
    \item \textbf{Phase 4: One-removal Swaps.} Replaces one lower-value accepted order in a compatible car route with a higher-value rejected order.
    \item \textbf{Phase 5: Limited Local Replacement.} Attempts a final, lightweight swap involving the last order of an existing car route to squeeze in better rejected orders.
\end{itemize}

On very small instances, a bounded exact DFS is used as a final improvement; this is automatically skipped on large hidden instances.