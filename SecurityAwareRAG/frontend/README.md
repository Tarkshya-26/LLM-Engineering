# Recorded evidence viewer

A static page that renders `data/demo.json`. It makes no security decision, no
network call, and no API call. Every value it displays is traceable to a
committed report in `../evaluation/reports/`.

## Serve

```
python3 -m http.server 8731 --directory frontend
```

Then open http://localhost:8731/

## Regenerate the data

```
python evaluation/security_eval.py --pipeline baseline  --phase 0 --repeat 8
python evaluation/security_eval.py --pipeline secure_p8 --phase 8 --repeat 8
python frontend/build_demo_data.py
python evaluation/validate_telemetry.py
```

## Reading the page

**Case-level evidence** is aggregated across every recorded run. A layer shown as
`enforced 8/8` produced a blocking or escalation decision on all eight runs.

**Selected run** panels show one recorded run and are labelled `recorded run N of
M`. They never represent the whole case — for POISON-01 the stored run is one
where the determination gate fired, while it fired on only 3 of 8 runs.

`enforced` and `constrained` are different things. Only `enforced` layers
refused something. `constrained` layers restricted or transformed data without
terminating the request, and are shown with their concrete evidence.
