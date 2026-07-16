# Extraction eval set (EFT-09)

Drop small representative PDFs here, then:

```
python scripts/eval_extraction.py run --tag baseline tests/eval/*.pdf
python scripts/eval_extraction.py run --tag jsonmode tests/eval/*.pdf
python scripts/eval_extraction.py compare baseline jsonmode
```

Results are written to `results/`. Use `--assert` for CI thresholds
(brief_present_rate==1.0, avg_chunk_success_rate>=0.90, avg_concepts>=5).
