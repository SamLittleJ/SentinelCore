"""Attack simulator and detection evaluation.

Drives a running SentinelCore through its public API: it signs a synthetic
organization's routine into it through ingestion, then plays attacks mapped
to MITRE ATT&CK, and compares the alerts that come back with what it did.
What is an attack and what is routine stays with the simulator; the server
only sees sign-ins, as it would in production.

Run it with `python -m simulator --help`.
"""
