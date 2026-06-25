# Next Steps

1. Add repeated trials for the most relevant b8 points if GPU time permits: no-control, request-cap 4, fixed-window 4, fixed-window 8, and dynamic CONCUR.
2. Consider a higher-pressure workload only if GPU availability allows and all runs remain Qwen-only, single-GPU, TP=1.
3. Add block-level cache allocation or eviction metrics only if SGLang exposes them in a stable endpoint or log format.
4. Keep mock and failed smoke runs excluded from Qwen performance claims.
