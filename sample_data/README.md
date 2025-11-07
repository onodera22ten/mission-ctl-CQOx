# CQOx Sample Datasets

This directory contains **3 sample datasets** designed to demonstrate CQOx's data preprocessing and causal inference capabilities. Each dataset requires different preprocessing steps and demonstrates different analytical challenges.

---

## Quick Start

1. **Start CQOx services:**
```bash
./START.sh
```

2. **Open the UI:**
```
http://localhost:4000
```

3. **Upload a sample dataset** using the file chooser

4. **Select domain** (education/medical/ecommerce)

5. **Click "Analyze"** to run comprehensive causal analysis

---

## Dataset 1: Education Study (CSV with Missing Data)

**File:** `education_messy.csv`
**Format:** CSV (Comma-separated)
**Rows:** 100 students
**Domain:** Education

### Description
A randomized controlled trial (RCT) evaluating the effect of tutoring programs on student test scores.

### Data Challenges
- **Missing values** in multiple columns (`test_score_raw`, `prior_gpa_text`)
- **Mixed data types** (numeric strings like "3.2", categorical age groups "15-16")
- **Text-encoded treatment** ("Yes"/"No" instead of 0/1)
- **Categorical encoding needed** (gender_code, household_income_range, parent_education)
- **Special values** ("N/A" in test scores)

### Columns
| Column Name | Type | Role | Description |
|------------|------|------|-------------|
| `student_id` | String | Unit ID | Unique student identifier |
| `name` | String | - | Student name (PII, should be dropped) |
| `age_group` | String | Covariate | Age bracket (15-16, 16-17, 17-18) |
| `test_score_raw` | String/Float | **Outcome** | Final test score (0-100, with missing values) |
| `received_tutoring` | String | **Treatment** | Whether student received tutoring ("Yes"/"No") |
| `prior_gpa_text` | String/Float | Covariate | GPA before intervention (0-4.0 scale) |
| `gender_code` | String | Covariate | Gender (F/M) |
| `missing_days` | Integer | Covariate | Days absent from school |
| `household_income_range` | String | Covariate | Family income bracket |
| `parent_education` | String | Covariate | Highest parent education level |

### Expected Preprocessing
1. **Parse test scores** - Convert "85.5" → 85.5, "N/A" → NaN
2. **Encode treatment** - "Yes" → 1, "No" → 0
3. **Handle missing values** - Impute or drop incomplete rows
4. **Encode categoricals** - One-hot or ordinal encoding for income, education
5. **Drop PII** - Remove `name` column

### Expected Results
- **Treatment Effect (ATE):** ~8-12 points increase in test scores
- **Heterogeneity:** Stronger effects for students with lower prior GPA
- **Confounders:** Prior GPA, parent education, household income

---

## Dataset 2: Medical Trial (Nested JSON)

**File:** `medical_trial.json`
**Format:** JSON (Nested structure)
**Rows:** 10 patients
**Domain:** Medical/Clinical Trial

### Description
A double-blind RCT testing a new hypertension drug (DrugA) vs. placebo. Includes longitudinal measurements across follow-up visits.

### Data Challenges
- **Nested JSON structure** (demographics, baseline_measurements, follow_up_visits)
- **Array of follow-up visits** - Need to extract final or average values
- **Missing data** (`"cholesterol_total": "Missing"`, withdrawn patients)
- **Unit parsing** required ("148mmHg" → 148, "220mg/dL" → 220)
- **Categorical Yes/No** fields need encoding
- **Longitudinal data** - Multiple time points per patient

### Structure
```json
{
  "study_metadata": { ... },
  "patient_records": [
    {
      "patient_id": "P001",
      "demographics": { "age": "45-54", "gender": "Male", ... },
      "baseline_measurements": { "systolic_bp": "148mmHg", ... },
      "treatment_assignment": "DrugA",
      "follow_up_visits": [
        { "week": 4, "systolic_bp": "142mmHg", ... },
        ...
      ],
      "final_outcome": { "achieved_target_bp": "Yes", ... }
    }
  ]
}
```

### Key Variables
| Variable | Type | Role | Extraction Path |
|----------|------|------|----------------|
| `patient_id` | String | Unit ID | `patient_records[].patient_id` |
| `treatment` | String | **Treatment** | `patient_records[].treatment_assignment` |
| `systolic_reduction` | Integer | **Outcome** | `patient_records[].final_outcome.systolic_reduction` |
| `age` | String | Covariate | `patient_records[].demographics.age` |
| `has_diabetes` | String | Covariate | `patient_records[].baseline_measurements.has_diabetes` |
| `baseline_bp` | String | Covariate | `patient_records[].baseline_measurements.systolic_bp` |

### Expected Preprocessing
1. **Flatten JSON** - Extract nested fields to tabular format
2. **Parse units** - "148mmHg" → 148, "220mg/dL" → 220
3. **Handle missingness** - "Missing" → NaN, withdrawn patients
4. **Aggregate longitudinal data** - Use final visit or average across visits
5. **Encode treatment** - "DrugA" → 1, "Placebo" → 0
6. **Encode Yes/No fields** - "Yes" → 1, "No" → 0

### Expected Results
- **Treatment Effect (ATE):** ~12-18 mmHg reduction in systolic BP
- **Heterogeneity:** Stronger effects in non-diabetic patients
- **Confounders:** Baseline BP, age, diabetes status

---

## Dataset 3: E-commerce Transactions (TSV with Complex Categoricals)

**File:** `ecommerce_transactions.xlsx.tsv`
**Format:** TSV (Tab-separated)
**Rows:** 50 transactions
**Domain:** E-commerce/Retail

### Description
Analysis of whether discount codes increase purchase amounts, controlling for customer characteristics and behavior.

### Data Challenges
- **Tab-separated format** (TSV, not CSV)
- **Currency strings** ("$1,245.99" needs parsing)
- **"MISSING" and "N/A" string values**
- **High-cardinality categoricals** (product_category, device_type, geographic_region)
- **Boolean as YES/NO strings**
- **Multiple confounders** - customer_segment, lifetime_value_tier, email_engagement, etc.

### Columns (Selected)
| Column Name | Type | Role | Description |
|------------|------|------|-------------|
| `transaction_id` | String | Unit ID | Unique transaction ID |
| `purchase_amount_usd` | String | **Outcome** | Total purchase ($1,245.99 format) |
| `received_discount_code` | String | **Treatment** | Whether discount was applied (YES/NO) |
| `customer_segment` | String | Covariate | Premium/Standard/Basic |
| `customer_lifetime_value_tier` | String | Covariate | High/Medium/Low Value |
| `days_since_last_purchase` | String/Integer | Covariate | Recency metric (may be "N/A") |
| `email_engagement_score` | Float | Covariate | 0-1 engagement metric |
| `time_on_site_minutes` | Float | Covariate | Session duration |
| `cart_abandonment_history` | String | Covariate | Low/Medium/High |
| `is_repeat_customer` | String | Covariate | TRUE/FALSE |

### Expected Preprocessing
1. **Parse currency** - "$1,245.99" → 1245.99
2. **Handle "MISSING"** - Replace with NaN
3. **Encode treatment** - "YES" → 1, "NO" → 0
4. **Encode booleans** - "TRUE" → 1, "FALSE" → 0
5. **Ordinal encoding** - customer_segment (Basic < Standard < Premium), lifetime_value_tier
6. **One-hot encoding** - product_category, device_type, payment_method
7. **Handle "N/A"** in days_since_last_purchase

### Expected Results
- **Treatment Effect (ATE):** Discount codes may **decrease** purchase amounts (selection bias - heavy discounters buy less)
- **Heterogeneity:** Positive effect for Premium customers, negative for Basic
- **Confounders:** Customer segment, lifetime value, engagement score, repeat customer status

---

## Data Quality Checks

CQOx automatically performs the following checks:

### ✅ Automatic Column Detection
- **Outcome (Y):** Numerical column with variance (test_score, systolic_reduction, purchase_amount)
- **Treatment (D):** Binary or categorical intervention variable
- **Unit ID:** Unique identifier per row
- **Covariates (X):** All other relevant features

### ✅ Automatic Domain Detection
Uses hierarchical classification:
- **Education:** Keywords like "student", "school", "grade", "test"
- **Medical:** Keywords like "patient", "treatment", "bp", "trial"
- **Retail:** Keywords like "transaction", "purchase", "customer"

### ✅ Estimator Validation
- Missing value tolerance
- Treatment/control balance
- Sample size requirements
- Panel structure (if time variable detected)
- Network topology (if adjacency data available)

---

## Usage Examples

### Example 1: CLI Upload
```bash
# Upload education dataset
curl -X POST http://localhost:8081/api/upload \
  -F "file=@sample_data/education_messy.csv" \
  -F "dataset_id=education_rct"

# Run analysis
curl -X POST http://localhost:8081/api/analyze/comprehensive \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "education_rct",
    "df_path": "/path/to/education_messy.csv",
    "mapping": {
      "y": "test_score_raw",
      "treatment": "received_tutoring"
    },
    "auto_select_columns": true
  }'
```

### Example 2: Python API
```python
import requests
import json

# Upload medical trial data
with open('sample_data/medical_trial.json', 'rb') as f:
    response = requests.post(
        'http://localhost:8081/api/upload',
        files={'file': f},
        data={'dataset_id': 'hypertension_trial'}
    )

# Run analysis with automatic preprocessing
result = requests.post(
    'http://localhost:8081/api/analyze/comprehensive',
    json={
        "dataset_id": "hypertension_trial",
        "df_path": "/path/to/medical_trial.json",
        "auto_select_columns": True
    }
).json()

print(f"ATE: {result['baseline_tau']:.3f} ± {result['baseline_se']:.3f}")
```

### Example 3: UI Workflow
1. Navigate to `http://localhost:4000`
2. Click "Choose file" → Select `ecommerce_transactions.xlsx.tsv`
3. Select domain: **Retail/E-commerce**
4. Click "Upload"
5. Review automatic column detection:
   - Outcome: `purchase_amount_usd`
   - Treatment: `received_discount_code`
   - Covariates: Auto-detected
6. Click "Analyze"
7. View results across 20 estimators with diagnostics

---

## Expected Output

### Estimators Run
All applicable estimators from the 20 available methods:
- Double ML (PLR, IRM)
- Propensity Score Methods (Matching, IPW)
- Sensitivity Analysis (E-values, Rosenbaum bounds)
- Instrumental Variables (if instrument detected)
- Causal Forests (for heterogeneity)
- And more...

### Visualizations Generated
- **Balance tables** - Covariate balance before/after matching
- **Propensity score overlap** - Distribution of e(X) for treated/control
- **CATE heterogeneity** - Treatment effect variation by subgroups
- **Sensitivity plots** - Robustness to unmeasured confounding
- **Diagnostic charts** - Quality gates, execution time, etc.

### Reports
- **HTML report** with all results and figures
- **LaTeX tables** for publication
- **JSON output** for programmatic access
- **Provenance log** for reproducibility

---

## Troubleshooting

### Issue: "CSV read failed"
- **Cause:** File format not recognized
- **Solution:** Check file extension (.csv for CSV, .json for JSON, .tsv for TSV)

### Issue: "No valid treatment column found"
- **Cause:** Treatment variable is not binary or has too many missing values
- **Solution:** Ensure treatment column has exactly 2 unique values (e.g., 0/1, Yes/No)

### Issue: "Insufficient sample size"
- **Cause:** Dataset too small for some estimators (e.g., Causal Forests needs n > 100)
- **Solution:** Use simpler estimators (Double ML, PSM) or combine with other datasets

### Issue: "All estimators failed"
- **Cause:** Data quality issues (all missing, no variance in outcome)
- **Solution:** Check data preprocessing logs in `logs/engine.log`

---

## Next Steps

After analyzing these sample datasets:

1. **Try your own data** - Upload CSV/JSON/TSV files with similar structure
2. **Explore heterogeneity** - Use Causal Forests to find subgroup effects
3. **Run sensitivity analysis** - Assess robustness to unmeasured confounding
4. **Generate publication-quality figures** - Export visualizations to `reports/`
5. **Review provenance logs** - Ensure full reproducibility

---

## Contact & Support

- **Documentation:** See main `README.md` for architecture details
- **Issues:** Report bugs or request features via GitLab issues
- **Sample data sources:** These are synthetic datasets generated for demonstration purposes

---

**CQOx - Rigorous Causal Inference with Real-World Data Challenges**
