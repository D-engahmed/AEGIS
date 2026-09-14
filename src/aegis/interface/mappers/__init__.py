"""Interface mappers: domain/application objects to wire schemas (layer 03).

Pure functions only — no FastAPI, no container, no store access. Routers do
auth, lookups, and auditing, then call these to build responses.
"""

from .catalog import dataset_out, target_out
from .evidence import provenance_out, record_out
from .experiments import experiment_out, snapshot_from_in, snapshot_out
from .policy import decision_out, verdict_out
from .results import metric_result_out
from .runs import run_out

__all__ = [
    "dataset_out",
    "decision_out",
    "experiment_out",
    "metric_result_out",
    "provenance_out",
    "record_out",
    "run_out",
    "snapshot_from_in",
    "snapshot_out",
    "target_out",
    "verdict_out",
]
