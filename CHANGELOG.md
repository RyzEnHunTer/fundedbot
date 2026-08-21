# CHANGELOG

## Version 0.1.0

### Phase 1 Complete

**Implemented**
- Workspace Separation (`qde/research/` vs `qde/production/`)
- Multi-Timeframe Data Layer (`mtf_manager.py`)
- Dynamic Feature Laboratory (`dynamic_generator.py`)
- Automated Feature Selection (`feature_selector.py`)

**Major Fixes**
- Eliminated MTF look-ahead bias by strictly adopting `label='left', closed='left'` for open-timestamped Forex data alignment.

**Verification**
- Independent QA Passed (Test Suite: `test_phase1.py` - 6/6 passing).

**Exit Gate**
- Passed.

**Architecture**
- Frozen.

**Status**
- Ready for Phase 2.
