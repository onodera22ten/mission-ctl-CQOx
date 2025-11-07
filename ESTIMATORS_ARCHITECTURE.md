# CQOx Estimators Architecture - Complete Overview

**Date**: 2025-10-28
**Status**: Integration of v1.0 estimators with v2.0 advanced methods

---

## 🎯 Current 7 Estimators (v1.0) - Position & Role

### **Status**: ✅ Implemented (Basic/Mock versions)
**Location**: `backend/engine/server.py` (lines 128-150)

```python
estimators_data = [
    ("tvce", tau, se),           # 1. Treatment-vs-Control Estimator
    ("ope", tau*1.1, se*0.9),    # 2. Observational Policy Evaluation
    ("hidden", tau*0.95, se),    # 3. Hidden Confounding
    ("iv", tau*0.85, se*1.1),    # 4. Instrumental Variables
    ("transport", tau*0.4, se*0.7), # 5. Transportability/External Validity
    ("proximal", tau*0.8, se*0.65), # 6. Proximal Causal Inference
    ("network", tau*0.5, se*0.6),   # 7. Network/Spillover Effects
]
```

---

## 📊 Estimators Hierarchy & Relationships

### **Tier 1: Foundational (Basic ATE Estimation)**

#### **1. TVCE (Treatment vs Control Estimator)** - v1.0 ✅
**Current Implementation**: Simple difference-in-means
**Position**: **Basic building block**

**What it is**:
```python
# Current (v1.0)
treated = df.loc[df[t]==1, y]
control = df.loc[df[t]==0, y]
tau = treated.mean() - control.mean()
```

**Relationship to v2.0**:
- **Double ML (PLR/IRM)** is the **advanced version** of TVCE
- Double ML adds:
  - Machine learning for confounding adjustment
  - Cross-fitting to avoid overfitting
  - Neyman orthogonality for valid inference

**Upgrade Path**:
```python
# v2.0 (Implemented)
from backend.inference.double_ml import estimate_ate_dml

# TVCE → Double ML upgrade
result_dml = estimate_ate_dml(X, y, treatment, method="irm")
# More robust, adjusts for X, valid SE
```

**Verdict**: TVCE is the **naive baseline**. Double ML is the **research-grade version**.

**Status**: ✅ **IMPLEMENTED** (2025-10-31)
- TVCE now uses Double ML-PLR for robust covariate-adjusted ATE estimation
- Implemented in `backend/engine/server.py` (lines 288-313)
- Fallback to baseline if covariates unavailable or estimation fails

---

#### **2. OPE (Observational Policy Evaluation)** - v1.0 ✅
**Current Implementation**: Mock (tau * 1.1)
**Position**: **Needs proper IPW/AIPW implementation**

**What it should be**:
- **Inverse Propensity Weighting (IPW)**
- **Augmented IPW (AIPW)** - doubly robust
- Used for policy evaluation from observational data

**Relationship to v2.0**:
- **Double ML (IRM)** already implements AIPW!
- DML-IRM = modern version of OPE

**Current v2.0 Implementation**:
```python
# backend/inference/double_ml.py (lines 180-220)
# IRM implements doubly-robust AIPW estimation
def fit_irm(self, X, y, d):
    # E[Y(1) - Y(0)]
    pseudo_outcome = g1_hat - g0_hat

    # AIPW correction (doubly robust)
    ipw_treated = (d / m_hat) * (y - g1_hat)
    ipw_control = ((1 - d) / (1 - m_hat)) * (y - g0_hat)

    psi = pseudo_outcome + ipw_treated - ipw_control
    return np.mean(psi)
```

**Verdict**: OPE mock should be **replaced by Double ML-IRM**. Already implemented!

**Status**: ✅ **IMPLEMENTED** (2025-10-31)
- OPE now uses Double ML-IRM (AIPW) for doubly-robust policy evaluation
- Implemented in `backend/engine/server.py` (lines 315-340)
- Provides robust inference even with model misspecification

---

### **Tier 2: Identification Strategies (Advanced Causal Designs)**

#### **3. Hidden Confounding** - v1.0 ⚠️
**Current Implementation**: Mock (tau * 0.95)
**Position**: **Needs sensitivity analysis**

**What it should be**:
- **Sensitivity Analysis** for unobserved confounding
- Methods:
  - Rosenbaum bounds
  - Oster's delta method
  - E-values
  - Partial identification (Manski bounds)

**NOT YET IMPLEMENTED in v2.0** ❌

**Needed Implementation**:
```python
# Future: backend/inference/sensitivity_analysis.py

from backend.inference.sensitivity_analysis import rosenbaum_bounds, oster_delta

# Rosenbaum bounds (how much unmeasured confounding to change conclusion)
bounds = rosenbaum_bounds(y, treatment, X, gamma_range=[1, 2, 3])

# Oster's delta (coefficient stability)
delta = oster_delta(y, treatment, X_baseline, X_full, R2_max=0.8)
```

**Verdict**: Mock needs to be **replaced by sensitivity analysis module** (Phase 2, Week 3)

---

#### **4. IV (Instrumental Variables)** - v1.0 ⚠️
**Current Implementation**: Mock (tau * 0.85)
**Position**: **Needs proper 2SLS/GMM implementation**

**What it should be**:
- **Two-Stage Least Squares (2SLS)**
- **GMM** for overidentified models
- **First-stage diagnostics** (weak instrument tests)

**Relationship to v2.0**:
- Can use **Double ML for IV** (Chernozhukov et al. 2018)
- More robust than traditional 2SLS

**NOT YET IMPLEMENTED in v2.0** ❌

**Needed Implementation**:
```python
# Future: backend/inference/instrumental_variables.py

from backend.inference.instrumental_variables import tsls, weak_instrument_test

# Traditional 2SLS
result = tsls(y, treatment, instruments, X, se_type="robust")

# Weak IV test
f_stat = weak_instrument_test(treatment, instruments, X)
if f_stat < 10:
    warnings.warn("Weak instruments detected (F < 10)")

# DML-IV (more robust)
result_dml = dml_iv(y, treatment, instruments, X)
```

**Verdict**: Mock needs **proper IV implementation** (Phase 2, Week 3)

---

### **Tier 3: External Validity & Generalization**

#### **5. Transport (Transportability/External Validity)** - v1.0 ⚠️
**Current Implementation**: Mock (tau * 0.4)
**Position**: **Needs generalizability framework**

**What it should be**:
- **IPSW** (Inverse Probability of Sampling Weighting)
- **Calibration weighting**
- Generalize from trial → target population

**NOT YET IMPLEMENTED in v2.0** ❌

**Needed Implementation**:
```python
# Future: backend/inference/transportability.py

from backend.inference.transportability import transport_ate

# Transport trial results to target population
result = transport_ate(
    y_trial, treatment_trial, X_trial,
    X_target,
    method="ipsw"  # or "calibration"
)
```

**Verdict**: Mock needs **generalization module** (Phase 3)

---

#### **6. Proximal (Proximal Causal Inference)** - v1.0 ⚠️
**Current Implementation**: Mock (tau * 0.8)
**Position**: **Needs proximal confounding methods**

**What it should be**:
- **Proximal Causal Inference** (Miao et al. 2018, Tchetgen Tchetgen et al. 2020)
- Use proxies for unmeasured confounders
- Bridge function estimation

**NOT YET IMPLEMENTED in v2.0** ❌

**Needed Implementation**:
```python
# Future: backend/inference/proximal_causal.py

from backend.inference.proximal_causal import proximal_ate

# Estimate ATE with confounding proxies
result = proximal_ate(
    y, treatment, X,
    W_confounder_proxy,  # Proxy for unmeasured confounder
    Z_treatment_proxy    # Proxy for treatment mechanism
)
```

**Verdict**: Mock needs **proximal causal module** (Advanced, Phase 4)

---

### **Tier 4: Network & Spillover Effects**

#### **7. Network (Network/Spillover Effects)** - v1.0 ⚠️
**Current Implementation**: Mock (tau * 0.5)
**Position**: **Needs interference/spillover methods**

**What it should be**:
- **Spillover effect estimation**
- **Network interference adjustment**
- Methods:
  - Horvitz-Thompson estimator
  - Inverse probability weighting for networks
  - Two-stage randomization inference

**PARTIALLY IMPLEMENTED** (Domain-specific figure only)
- Network figures: `backend/engine/figures_finance_network_policy.py`
- But no actual network estimator

**Needed Implementation**:
```python
# Future: backend/inference/network_effects.py

from backend.inference.network_effects import estimate_spillover

# Estimate direct and spillover effects
result = estimate_spillover(
    y, treatment, network_adj_matrix,
    method="horvitz_thompson"
)

print(f"Direct effect: {result.direct_effect}")
print(f"Spillover effect: {result.spillover_effect}")
print(f"Total effect: {result.total_effect}")
```

**Verdict**: Mock needs **network causal inference module** (Phase 3-4)

---

## 🏗️ Architecture Integration Plan

### **Current State (v1.0)**
```
server.py:
  ├── 7 mock estimators (simple formulas)
  ├── Basic figures (14 + 6 primitives + 26 domain)
  └── Provenance + Validation
```

### **Target State (v2.0 Integrated)**
```
CQOx v2.0 Architecture:
  ├── Tier 1: Basic ATE
  │   ├── TVCE (simple) → Replaced by Double ML ✅
  │   └── OPE (mock) → Replaced by Double ML-IRM ✅
  │
  ├── Tier 2: Advanced Identification
  │   ├── Double ML (PLR/IRM) ✅ NEW
  │   ├── Synthetic Control ⏳ (Week 2)
  │   ├── IV (2SLS/GMM) ⏳ (Week 3)
  │   ├── Regression Discontinuity ⏳ (Week 3)
  │   └── Difference-in-Differences ⏳ (Week 3)
  │
  ├── Tier 3: Heterogeneity & ML
  │   ├── Causal Forests ⏳ (Week 2)
  │   ├── Metalearners (S/T/X/R) ⏳ (Phase 3)
  │   └── CATE Estimation ⏳ (Phase 3)
  │
  ├── Tier 4: Robustness & Sensitivity
  │   ├── Sensitivity Analysis (Hidden) ⏳ (Week 3)
  │   ├── Placebo Tests ⏳ (Week 2)
  │   └── Specification Curves ⏳ (Phase 3)
  │
  ├── Tier 5: Generalization
  │   ├── Transportability ⏳ (Phase 3)
  │   └── External Validity ⏳ (Phase 3)
  │
  ├── Tier 6: Networks & Panels
  │   ├── Network Effects ⏳ (Phase 4)
  │   ├── Proximal Causal ⏳ (Phase 4)
  │   └── Panel Methods (TWFE, Staggered DiD) ⏳ (Phase 3)
  │
  └── Infrastructure (v2.0) ✅
      ├── Cluster-Robust SE ✅
      ├── Bootstrap Inference ✅
      ├── LaTeX Tables ✅
      ├── Balance Tables ✅
      └── Randomization Inference ⏳
```

---

## 🔄 Migration Strategy: v1.0 → v2.0

### **Step 1: Replace Mocks with Real Implementations** (Week 2-3)

#### Replace TVCE mock:
```python
# OLD (v1.0)
tau = treated.mean() - control.mean()

# NEW (v2.0)
from backend.inference.double_ml import estimate_ate_dml
result = estimate_ate_dml(X, y, treatment, method="irm")
tau = result.theta
```

#### Replace OPE mock:
```python
# OLD (v1.0)
tau_ope = tau * 1.1  # Mock

# NEW (v2.0)
# OPE is already in DML-IRM (doubly robust)
result = estimate_ate_dml(X, y, treatment, method="irm")
# IRM implements AIPW = modern OPE
```

#### Keep other mocks for now, implement in phases:
- **IV**: Week 3 (proper 2SLS/GMM)
- **Hidden**: Week 3 (sensitivity analysis)
- **Transport**: Phase 3 (generalization)
- **Proximal**: Phase 4 (advanced)
- **Network**: Phase 4 (advanced)

---

### **Step 2: Add Advanced Methods Alongside** (Week 2-3)

New estimators that don't replace existing:
- **Synthetic Control** (Week 2)
- **Causal Forests** (Week 2)
- **Regression Discontinuity** (Week 3)
- **Staggered DiD** (Week 3)

These are **additional** capabilities, not replacements.

---

### **Step 3: Create Unified API** (Week 4)

```python
# Future: backend/inference/estimator_factory.py

class EstimatorFactory:
    """Unified interface for all estimators"""

    @staticmethod
    def estimate(
        method: str,
        data: pd.DataFrame,
        outcome: str,
        treatment: str,
        covariates: List[str],
        **kwargs
    ) -> EstimatorResult:
        """
        Unified estimation interface

        Methods:
        - "double_ml": Double/Debiased ML (✅ Implemented)
        - "synthetic_control": Synthetic control (⏳ Week 2)
        - "causal_forest": Causal forests (⏳ Week 2)
        - "iv": Instrumental variables (⏳ Week 3)
        - "did": Difference-in-Differences (⏳ Week 3)
        - "rd": Regression Discontinuity (⏳ Week 3)
        - "sensitivity": Sensitivity analysis (⏳ Week 3)
        - "transport": Transportability (⏳ Phase 3)
        """

        if method == "double_ml":
            from backend.inference.double_ml import estimate_ate_dml
            return estimate_ate_dml(...)

        elif method == "synthetic_control":
            from backend.inference.synthetic_control import synth_control
            return synth_control(...)

        elif method == "causal_forest":
            from backend.inference.causal_forests import causal_forest_ate
            return causal_forest_ate(...)

        # ... etc
```

---

## 📊 Comparison: v1.0 vs v2.0 Estimators

| Estimator | v1.0 Status | v2.0 Status | Implementation Priority |
|-----------|-------------|-------------|------------------------|
| **TVCE** | Mock | → **Double ML-PLR** ✅ | **COMPLETED** - server.py line 288-313 |
| **OPE** | Mock | → **Double ML-IRM** ✅ | **COMPLETED** - server.py line 315-340 |
| **Hidden** | Mock | → **Sensitivity Analysis** ⏳ | Week 3 |
| **IV** | Mock | → **2SLS/GMM** ⏳ | Week 3 |
| **Transport** | Mock | → **IPSW/Calibration** ⏳ | Phase 3 |
| **Proximal** | Mock | → **Bridge Functions** ⏳ | Phase 4 |
| **Network** | Mock | → **Horvitz-Thompson** ⏳ | Phase 4 |
| **Synthetic Control** | ❌ | **Abadie et al.** ⏳ | Week 2 |
| **Causal Forests** | ❌ | **Athey & Imbens** ⏳ | Week 2 |
| **RD** | ❌ | **Local polynomial** ⏳ | Week 3 |
| **DiD** | ❌ | **Staggered** ⏳ | Week 3 |

---

## 🎯 Recommendations

### **Immediate Actions** (Week 2)

1. **Keep v1.0 mocks for now** - Don't break existing system
2. **Add v2.0 methods alongside** - Coexist during transition
3. **Create unified API** - Single interface for all methods
4. **Document relationships** - Users understand when to use what

### **Phased Replacement** (Week 3-4)

```python
# Phase 1: Run both (Week 2-3)
results = {
    "tvce_v1": tvce_mock(),           # Old
    "tvce_v2": double_ml_plr(),       # New
    "ope_v1": ope_mock(),             # Old
    "ope_v2": double_ml_irm(),        # New
}

# Phase 2: Switch default (Week 4)
results = {
    "ate": double_ml_irm(),           # Primary
    "ate_naive": tvce_simple(),       # Comparison
}

# Phase 3: Deprecate mocks (Phase 3)
# Remove v1.0 mocks entirely
```

---

## 💡 Summary

### **7 v1.0 Estimators - Current Role**:

1. **TVCE** → Placeholder for **Double ML** ✅ (already replaced)
2. **OPE** → Placeholder for **Double ML-IRM** ✅ (already replaced)
3. **Hidden** → Needs **Sensitivity Analysis** ⏳
4. **IV** → Needs **proper 2SLS/GMM** ⏳
5. **Transport** → Needs **IPSW/Calibration** ⏳
6. **Proximal** → Needs **bridge functions** ⏳
7. **Network** → Needs **interference methods** ⏳

### **v2.0 Position**:

- **Double ML** (✅ Implemented) **replaces** TVCE + OPE
- Remaining 5 mocks become **real implementations** in Weeks 2-4
- Additional methods (Synthetic Control, Causal Forests, etc.) are **new capabilities**

### **Architecture**:

```
v1.0: 7 mock estimators (simple)
       ↓
v2.0: 20+ real estimators (research-grade)
       ├── Replace 2 mocks (TVCE → DML, OPE → DML-IRM) ✅
       ├── Upgrade 5 mocks (Hidden, IV, Transport, Proximal, Network) ⏳
       └── Add 10+ new methods (Synth Control, Forests, RD, DiD, ...) ⏳
```

**Conclusion**: v1.0 estimators are **placeholders**. v2.0 provides **real implementations** that researchers can publish with.

---

**Generated**: 2025-10-28
**Next**: Continue Week 2 (Synthetic Control, Causal Forests, Diagnostics)
