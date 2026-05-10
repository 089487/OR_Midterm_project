This Markdown document is designed for **Problem 4: Numerical Experiments** section. It incorporates the large-scale configuration ($n_C = 1,000$), the random long-term horizon ($n_D$ up to 100 days), and the normalized budget logic ($B \propto n_D$).

---

# Numerical Study: Scenario Design and Scalability Analysis

To evaluate the robustness and scalability of our proposed heuristic algorithm, we conducted a comprehensive numerical study. We generated **750 test instances** across **25 distinct scenarios**, with each scenario containing 30 random instances. The planning horizon $n_D$ for each instance is randomly sampled from $[7, 100]$ days to simulate various business operational cycles.

## 1. Experimental Parameters and Normalization

To maintain consistency in large-scale testing, the following parameters are fixed or scaled:
*   **Total Stations ($n_S$):** 100
*   **Total Fleet Size ($n_C$):** 1,000 cars
*   **Car Levels ($n_L$):** 10
*   **Budget Normalization ($B$):** To ensure a consistent "relocation pressure" across different time horizons, the moving budget is defined as a function of the planning days:
    *   **Tight:** $B = 30 \times n_D$ (approx. 30 mins per day).
    *   **Moderate:** $B = 300 \times n_D$ (approx. 5 hours per day).
    *   **Infinite:** $B = 1,000,000$.

## 2. Factorial Design

The experiments analyze five primary factors:
1.  **System Load ($n_K : n_C$):** Ranges from 1:3 (Sparse) to 10:1 (Extreme Overload).
2.  **Level Mismatch:** Compares uniform distribution with an **8:2 Skew** (80% of orders are for odd-tier cars, while 80% of cars are even-tier), stressing the upgrade mechanism.
3.  **Spatial Flow:**
    *   *Odd/Even:* A forced imbalance where cars start at odd stations but orders move from even to odd.
    *   *Hub Effect (1G/2G/3G):* 5, 10, or 15 stations act as "car graveyards" where the return probability is 50x higher than average.
4.  **Temporal Skewness:**
    *   *Weekend:* Concentrations of demand on Friday, Saturday, and Sunday.
    *   *Peak (1 or 3):* Bursts of demand centered around specific dates following a Normal distribution $N(\mu, \sigma^2)$.
5.  **Relocation Constraint:** Testing the impact of the budget $B$ on total profit.

---

## 3. The Scenario Matrix

| Group | ID | Load Ratio | Level Dist. | Station Dist. | Time Dist. | Budget ($B$) | Insight Focus |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Base** | S1 | 1 : 1 | Random | Random | Random | 1,000,000 | Baseline performance |
| **Load** | S2 | **10 : 1** | Random | Random | Random | 1,000,000 | Resource idle rate |
| | S3 | **1 : 3** | Random | Random | Random | 1,000,000 | Capacity sufficiency |
| | S4 | **3 : 1** | Random | Random | Random | 1,000,000 | Order selection logic |
| **Level** | S5 | 1 : 1 | **8:2 Skew** | Random | Random | 1,000,000 | Upgrade efficiency |
| **Spatial** | S6 | 1 : 1 | Random | **Odd/Even** | Random | 1,000,000 | Relocation necessity |
| | S7 | 1 : 1 | Random | **Odd/Even** | Random | **$300 \times n_D$** | Relocation cost-benefit |
| | S8 | 1 : 1 | Random | **Hub (1G)** | Random | **$300 \times n_D$** | Single hotspot pressure |
| | S9 | 1 : 1 | Random | **Hub (2G)** | Random | **$300 \times n_D$** | Multiple hotspot pressure |
| | S10 | 1 : 1 | Random | **Hub (3G)** | Random | 1,000,000 | Hub drain capacity |
| | S11 | 1 : 1 | Random | **Hub (3G)** | Random | **$300 \times n_D$** | Budgeted hub recovery |
| **Time** | S12 | 1 : 1 | Random | Random | **Weekend** | 1,000,000 | Periodical peaks |
| | S13 | 1 : 1 | Random | Random | **Peak (1)** | 1,000,000 | Single burst resilience |
| | S14 | 1 : 1 | Random | Random | **Peak (3)** | 1,000,000 | Iterative burst recovery |
| **Budget** | S15 | 1 : 1 | Random | Random | Random | **0** | Minimum baseline profit |
| | S16 | 1 : 1 | Random | Random | Random | **$30 \times n_D$** | Tight labor constraints |
| | S17 | 1 : 1 | Random | Random | Random | **$300 \times n_D$** | ROI of moving budget |
| **Mixed** | S18 | 3 : 1 | 8:2 Skew | Odd/Even | Weekend | $300 \times n_D$ | Complex environment A |
| | S19 | 3 : 1 | 8:2 Skew | Odd/Even | Weekend | **$30 \times n_D$** | High-pressure mismatch |
| | S20 | 3 : 1 | 8:2 Skew | Odd/Even | Weekend | 1,000,000 | Best-case for mismatch |
| | S21 | 3 : 1 | 8:2 Skew | Hub (3G) | Weekend | **$30 \times n_D$** | Hub recovery pressure |
| | S22 | 3 : 1 | 8:2 Skew | Hub (3G) | Weekend | $300 \times n_D$ | Integrated logistics ROI |
| | S23 | 3 : 1 | 8:2 Skew | Hub (3G) | Weekend | 1,000,000 | Competitive bound |
| **Stress**| S24 | **10 : 1** | 8:2 Skew | Odd/Even | Weekend | $30 \times n_D$ | **Full system stress test A**|
| | S25 | **10 : 1** | 8:2 Skew | Hub (3G) | Weekend | $30 \times n_D$ | **Full system stress test B**|

---

## 4. Analytical Methodology

Our analysis focuses on three core performance metrics:
1.  **Profitability and Recovery:** We measure the "Profit Improvement" of our heuristic against a *Baseline FCFS* algorithm (which allows no upgrades and no relocations). We expect to show that as $n_D$ increases to 100 days, the cumulative advantage of intelligent relocation significantly widens.
2.  **Shadow Price of Budget:** By analyzing S15, S16, and S17, we calculate the marginal profit per minute of $B$. This identifies the optimal point where increasing relocation staff no longer yields significant returns.
3.  **Big-O Performance:** With $n_C = 1,000$ and $n_K = 10,000$, we record execution times to verify that the algorithm remains within the **3-minute computational limit** provided by IEDO company, even for quarterly horizons.