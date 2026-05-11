This updated **Numerical Study** section (Markdown format) is tailored for 14-scenario design. It emphasizes the scaled budget logic ($B \propto n_D$) and the fixed fleet size ($n_C = 100$), providing the academic justification Prof. Kung looks for.

---

# Numerical Study: Scenario Design and Sensitivity Analysis

To rigorously evaluate the performance of our heuristic algorithm for the IEDO car rental problem, we designed **14 distinct scenarios**. This study focuses on how external factors—such as supply-demand ratios, geographical imbalances, and relocation budgets—affect total profitability and operational efficiency.

## 1. Experimental Setup and Normalization

To evaluate the robustness of our heuristic algorithm under diverse business conditions, we generated **420 random instances** with high variability in fleet and pricing structures:

*   **Fleet Size ($n_C$):** $n_C \sim U(20, 70)$.
*   **Service Tiers ($n_L$):** The number of car levels is randomized between 2 and 10 per instance.
*   **Dynamic Pricing:** Hourly rates are generated using a cumulative random process to ensure $Rate_{l+1} > Rate_l$, reflecting realistic premium pricing for higher-tier vehicles.
*   **System Load ($n_K$):** $n_K = \text{ratio} \times n_C$.
*   **Budget Scaling ($B$):**
    *   **Tight Budget:** $B = 30 \times n_D$.
    *   **Moderate Budget:** $B = 300 \times n_D$.
    
## 2. Experimental Factors

| Group | Factor | Description |
| :--- | :--- | :--- |
| **Load** | $n_K : n_C$ | Testing the system from sparse demand (1:10) to heavy overload (3:1). |
| **Level** | Tier Distribution | Testing an **8:2 Skew** (80% low-tier orders vs. 80% high-tier cars) to stress the "+1 level" upgrade rule. |
| **Spatial** | Flow Dynamics | **Odd/Even:** Mandatory relocation from even to odd stations. <br> **Hub Effect:** Return probability concentrated in specific station groups. |
| **Temporal** | Demand Arrival | **Weekend:** Periodic 3-day peaks. <br> **Peak (1 or 3):** Sudden bursts of demand modeled via Normal distribution. |
| **Finance** | Budget $B$ | Measuring the ROI of every minute spent on car relocation. |

---

## 3. Updated Scenario Matrix

| ID | Focus Dimension | Load Ratio | Level Dist. | Station Dist. | Time Dist. | Budget ($B$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **S01** | **Baseline Case** | 1 : 1 | Random | Random | Random | 1,000,000 |
| **S02** | Load (Ultra-Low) | **1 : 10** | Random | Random | Random | 1,000,000 |
| **S03** | Load (Low) | **1 : 3** | Random | Random | Random | 1,000,000 |
| **S04** | Load (High) | **3 : 1** | Random | Random | Random | 1,000,000 |
| **S05** | Level Mismatch | 1 : 1 | **8:2 Skew** | Random | Random | 1,000,000 |
| **S06** | Forced Relocation | 1 : 1 | Random | **Odd/Even** | Random | **$300 \times n_D$** |
| **S07** | Hub Effect (1G) | 1 : 1 | Random | **Hub (1G)** | Random | **$300 \times n_D$** |
| **S08** | Hub Effect (2G) | 1 : 1 | Random | **Hub (2G)** | Random | **$300 \times n_D$** |
| **S09** | Periodical Peaks | 1 : 1 | Random | Random | **Weekend** | 1,000,000 |
| **S10** | Sudden Burst (1) | 1 : 1 | Random | Random | **Peak (1)** | 1,000,000 |
| **S11** | Sudden Burst (3) | 1 : 1 | Random | Random | **Peak (3)** | 1,000,000 |
| **S12** | Budget (Zero) | 1 : 1 | Random | Random | Random | **0** |
| **S13** | Budget (Tight) | 1 : 1 | Random | Random | Random | **$30 \times n_D$** |
| **S14** | Budget (Moderate) | 1 : 1 | Random | Random | Random | **$300 \times n_D$** |

---

## 4. Analytical Methodology

By comparing the results across these 14 scenarios, our report will provide insights into:

1.  **Staffing Optimization:** Using S12, S13, and S14 to determine the "Shadow Price" of relocation budget. We identify the threshold where increasing $B$ no longer significantly reduces the rejection compensation costs.
2.  **Upgrade Strategy Efficacy:** Analyzing S05 to evaluate if the limited upgrade rule (+1 level) provides enough flexibility to sustain profitability when the fleet composition is suboptimal.
3.  **Temporal Resilience:** Evaluating S09-S11 to see if the algorithm accounts for the 4.5-hour recovery window (cleaning + ready buffer) during high-frequency demand bursts.
4.  **Spatial Resource Balance:** Observing if the algorithm effectively manages "Car Graveyards" in S07-S08 by proactively moving cars out of high-return hubs to low-supply areas.

---

### Pro-Tip for your Report:
When you present the results of **S06 (Odd/Even)** vs. **S12 (Zero Budget)**, you will likely see a massive gap. This is the strongest evidence that your relocation logic is working. Use a **Box Plot** or **Histogram** to show the profit distribution for these specific scenarios to prove the robustness of your heuristic.

