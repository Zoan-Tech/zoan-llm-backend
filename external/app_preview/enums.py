from enum import StrEnum

class BuildStatus(StrEnum):
    """Status of an app preview build."""
    STARTING = "starting"
    BUILDING = "building"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    DELETED = "deleted"