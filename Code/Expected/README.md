# Expected Table

This folder is optional. By default, `Code/Evaluate.py` uses:

```text
Code/Input/Target.csv
```

If you want a separate reference CSV, place it here as:

```text
Code/Expected/table.csv
```

and run:

```bash
python3 Code/Evaluate.py --expected Code/Expected/table.csv
```

The predicted table is:

```text
Code/Output/Table.csv
```
