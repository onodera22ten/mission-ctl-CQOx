# Intelligent Figure Selection System (Task ⑩)

## Overview

The **Intelligent Figure Selection System** automatically determines which domain-specific visualizations to generate based on data availability, quality, and relevance. This ensures that only meaningful and appropriate figures are created, preventing wasted computation and improving user experience.

## Architecture

### Components

1. **FigureSelector** (`backend/engine/figure_selector.py`)
   - Evaluates data prerequisites for each domain figure
   - Calculates confidence scores based on data quality
   - Provides selection reports with detailed reasoning

2. **DomainFigureGenerator** (updated in `backend/engine/figures_domain.py`)
   - Integrates FigureSelector for intelligent generation
   - Only creates figures that pass selection criteria
   - Logs selection decisions for transparency

3. **API Integration** (updated in `backend/engine/server.py`)
   - Exposes figure selection report in API response
   - Shows users which figures were generated and why

## How It Works

### Selection Criteria

Each domain-specific figure has defined requirements:

```python
FIGURE_REQUIREMENTS = {
    "medical_dose_response": {
        "required_columns": ["y", "dose"],
        "min_rows": 30,
        "min_dose_levels": 3,
        "description": "Dose-response relationship"
    },
    # ... 26 total figures
}
```

### Decision Logic

For each figure, the selector checks:

1. **Required Columns**: Must exist in data
   - From role mapping (y, treatment, time, etc.)
   - Or from specific column names (dose, teacher_id, etc.)

2. **Optional Columns**: Improve quality if present
   - Used for confidence scoring

3. **Data Quality Thresholds**:
   - Minimum row count
   - Minimum number of groups/clusters
   - Minimum time periods
   - Sufficient dose levels

4. **Confidence Scoring**:
   - Start at 1.0 (perfect)
   - Reduce for missing optional columns
   - Reduce for low group counts
   - Generate if confidence ≥ 0.6

### Example Selection Process

```
[FigureSelector] Evaluating 6 figures for medical domain
[FigureSelector] ✓ medical_km_survival: All requirements met
[FigureSelector] ✗ medical_dose_response: Missing required: dose
[FigureSelector] ✓ medical_cluster_effect: Partial requirements (confidence: 0.80)
[FigureSelector] ✗ medical_adverse_events: Missing required: adverse_event
[FigureSelector] ✓ medical_iv_candidates: All requirements met
[FigureSelector] ✓ medical_sensitivity: All requirements met

Result: Generating 4/6 figures
```

## Domain-Specific Figures

### Medical Domain (6 figures)

1. **medical_km_survival**: KM-style survival curves
   - Required: y, treatment
   - Min rows: 50

2. **medical_dose_response**: Dose-response relationship
   - Required: y, dose
   - Min rows: 30
   - Min dose levels: 3

3. **medical_cluster_effect**: Facility/provider cluster effects
   - Required: y, treatment, cluster_id/site_id
   - Min rows: 100
   - Min clusters: 3

4. **medical_adverse_events**: Adverse event risk map
   - Required: treatment, adverse_event
   - Min rows: 50

5. **medical_iv_candidates**: Natural experiment IV candidates
   - Required: y, treatment
   - Min rows: 100

6. **medical_sensitivity**: Rosenbaum sensitivity analysis
   - Required: y, treatment
   - Min rows: 50

### Education Domain (5 figures)

1. **education_gain_distrib**: Achievement gain distribution
   - Required: y, treatment
   - Min rows: 50

2. **education_teacher_effect**: Teacher/class heterogeneity
   - Required: y, teacher_id/class_id
   - Min rows: 100
   - Min groups: 5

3. **education_attainment_sankey**: Achievement transition Sankey
   - Required: y
   - Min rows: 50

4. **education_event_study**: Program introduction timeline
   - Required: y, treatment, time
   - Min rows: 100
   - Min time periods: 5

5. **education_fairness**: Subgroup fairness analysis
   - Required: y, treatment
   - Min rows: 100

### Retail Domain (5 figures)

1. **retail_uplift_curve**: Customer targeting uplift
   - Required: y, treatment
   - Min rows: 100

2. **retail_price_iv**: Price-demand IV analysis
   - Required: y, price
   - Min rows: 50

3. **retail_channel_effect**: Channel-specific effects
   - Required: y, treatment, channel
   - Min rows: 100
   - Min groups: 2

4. **retail_inventory_heat**: Inventory constraint timeline
   - Required: time, inventory
   - Min rows: 50

5. **retail_spillover**: Network spillover (recommendations)
   - Required: None (always generated)
   - Min rows: 50

### Finance Domain (4 figures)

1. **finance_pnl**: P&L breakdown by treatment
2. **finance_portfolio**: Portfolio allocation split
3. **finance_risk_return**: Risk-return tradeoff
4. **finance_macro**: Macro sensitivity analysis

### Network Domain (3 figures)

1. **network_spillover_heat**: Network spillover heatmap
2. **network_graph**: Network graph visualization
3. **network_interference**: Interference-adjusted ATE

### Policy Domain (3 figures)

1. **policy_did**: Difference-in-Differences panel
2. **policy_rd**: Regression Discontinuity design
3. **policy_geo**: Geographic policy impact map

## API Response Format

```json
{
  "figure_selection": {
    "total_available": 6,
    "generated": 4,
    "skipped": 2,
    "generated_list": [
      "medical_km_survival",
      "medical_cluster_effect",
      "medical_iv_candidates",
      "medical_sensitivity"
    ],
    "skipped_list": [
      "medical_dose_response",
      "medical_adverse_events"
    ]
  }
}
```

## Usage Example

### Python API

```python
from backend.engine.figure_selector import FigureSelector
import pandas as pd

# Load data
df = pd.read_csv("medical_trial.csv")
mapping = {
    "y": "outcome",
    "treatment": "drug",
    "unit_id": "patient_id"
}

# Create selector
selector = FigureSelector(df, mapping, domain="medical")

# Get recommendations
recommended = selector.get_recommended_figures()
print(f"Generating {len(recommended)} figures: {recommended}")

# Get detailed report
report = selector.get_selection_report()
print(f"Domain: {report['domain']}")
print(f"Recommended: {report['recommended']}/{report['total_figures']}")

for fig_name, details in report['details'].items():
    print(f"{fig_name}: {details['reason']}")
```

### Integrated Usage

The system is automatically integrated into the analysis pipeline:

```python
# In server.py
generator = DomainFigureGenerator(df, mapping, domain)
figures = generator.generate_all(output_dir)
# Only recommended figures are generated
```

## Benefits

### 1. Performance Optimization
- Skips figures that cannot be generated
- Reduces wasted computation
- Faster analysis completion

### 2. User Experience
- Only shows meaningful visualizations
- Provides clear reasoning for skipped figures
- Transparent decision-making

### 3. Data Quality Awareness
- Highlights missing data requirements
- Guides users on data collection
- Suggests improvements for better analysis

### 4. Scalability
- Easy to add new figures
- Declarative requirements specification
- Consistent evaluation logic

## Implementation Details

### Adding New Figures

To add a new domain-specific figure:

1. **Define requirements** in `FIGURE_REQUIREMENTS`:

```python
"medical_new_figure": {
    "required_columns": ["y", "treatment", "biomarker"],
    "optional_columns": ["age", "sex"],
    "min_rows": 100,
    "min_groups": 3,
    "description": "Biomarker stratification analysis"
}
```

2. **Implement generation method** in `DomainFigureGenerator`:

```python
def _medical_new_figure(self, output_dir: Path) -> Optional[Path]:
    if not self._should_generate("medical_new_figure"):
        return None
    # ... implementation
```

3. **Add to domain method**:

```python
def _generate_medical(self, output_dir: Path) -> Dict[str, str]:
    figures = {}
    # ... existing figures

    if self._should_generate("medical_new_figure"):
        fig_path = self._medical_new_figure(output_dir)
        if fig_path:
            figures["medical_new_figure"] = str(fig_path)

    return figures
```

### Confidence Calculation

Confidence starts at 1.0 and is reduced by:

- **0.7x**: Missing optional but useful columns
- **0.8x**: Below recommended group count
- **0.7x**: Below recommended time periods

Threshold for generation: **0.6**

This allows figures to be generated with partial data while prioritizing high-quality visualizations.

## Future Enhancements

### Planned Improvements

1. **Machine Learning Selection**
   - Train model on historical figure usefulness
   - Predict which figures users find most valuable
   - Adaptive selection based on domain and use case

2. **Dynamic Requirements**
   - Adjust thresholds based on dataset size
   - Domain-specific quality criteria
   - User preference learning

3. **Interactive Selection**
   - Allow users to request specific figures
   - Override automatic decisions
   - Custom figure templates

4. **Quality Scoring**
   - Rate figure quality after generation
   - Detect anomalies and warn users
   - Suggest data improvements

## Testing

Run tests:

```bash
pytest tests/test_figure_selector.py -v
```

## References

- Task ⑩: Domain-specific visualization auto-judgment system
- Col2 Specification: Domain-tailored visualizations
- `backend/engine/figure_selector.py`: Core implementation
- `backend/engine/figures_domain.py`: Integration
