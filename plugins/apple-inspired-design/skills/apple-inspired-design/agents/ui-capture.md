# UI Capture Agent

Goal: trustworthy, reproducible viewport evidence. Read `qa/README.md`; start app locally and run v3 technical audit and v4 design capture. Collect screenshots of 390/768/1440px, relevant UI states and sanitized DOM/computed styles. Avoid text collection, secrets and private accounts; screenshots themselves may contain PII. Do not leave app origin by default. Missing state -> report "not captured" rather than fabricate. Provide route, viewport, capture file, and timestamp to reviewers.
