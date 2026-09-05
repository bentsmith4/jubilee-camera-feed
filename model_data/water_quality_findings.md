# Public water-quality research findings

## 2026-09-05 initial ingest/backtest

The automated ingest successfully retrieved **7,650 normalized observations from 9 public stations**: 3,417 ADEM/EPA Eastern Shore beach-monitoring rows and 4,233 Alabama Water Watch Magnolia River rows.

The dataset includes 3,417 Enterococcus observations plus regional physical-water-quality observations including 377 dissolved-oxygen measurements, 377 DO-saturation measurements, 215 salinity measurements, 567 water-temperature measurements, 376 turbidity measurements and 207 Secchi-depth measurements. Magnolia River measurements remain regional proxies and are not local Eastern Shore bottom-water measurements.

The verified event database was expanded to six confirmed events, including 2020-09-07 Fairhope, 2024-06-12 Point Clear, 2024-08-05 Eastern Shore, 2025-07-17 Fairhope, 2026-08-29 Fairhope-Point Clear multi-pocket and 2026-08-30 localized Fairhope north-of-pier.

Four confirmed historical events overlap the public water-quality period closely enough to produce antecedent observations. The exploratory backtest generated 109 event-linked observations across tested windows. **No stable Enterococcus signal emerged.** Most MPN comparisons were identical to or lower than same-month controls; isolated higher/lower cfu comparisons were based on one linked event and are not generalizable. Therefore Enterococcus remains a contextual runoff proxy with **zero production forecast weight**.

The current sample is still insufficient for feature promotion: only four confirmed events have overlapping water-quality observations versus the policy threshold of at least ten distinct events plus formal out-of-sample validation. The next research priorities are: (1) recover additional exact-date 2005-2025 Jubilee events; (2) ingest Mobile Baykeeper Live Oak/Point Clear and Fly Creek historical series into normalized rows; (3) improve geography-aware matching so station/event comparisons respect shoreline cell; (4) test Magnolia River DO/salinity/turbidity only where temporal coverage overlaps events; and (5) combine antecedent water-quality state with observed rainfall/river discharge rather than testing bacteria in isolation.

No production probability weights or user alert thresholds were changed by this research pass.
