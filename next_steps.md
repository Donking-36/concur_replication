# Next Steps

1. Commit and push the completed v2 reproduction artifacts after one final `git status --short` review.
2. Keep mock, failed smoke, and context-length failure runs excluded from Qwen performance claims except as documented limitations.
3. If more GPU time is available, repeat P6 b12/b16 pressure runs across seeds 1/2 to reduce single-run variance.
4. Tune `concur_dynamic_v2` thresholds against exact SGLang metrics, especially `U_high`, `W_max`, and `alpha`, because fixed_window_4 remains the best b8/b12 latency point.
5. Consider a multi-GPU serving experiment only if hardware is explicitly available; current results are single-GPU scaled reproduction evidence.
