from django.db import models


class SyncRun(models.Model):
    ats_source = models.CharField(max_length=50)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("running", "Running"), ("success", "Success"), ("failed", "Failed")],
        default="running",
    )
    since = models.DateTimeField(null=True, blank=True)
    cursor = models.DateTimeField(null=True, blank=True)
    pulled = models.IntegerField(default=0)
    pushed = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    created = models.IntegerField(default=0)
    updated = models.IntegerField(default=0)
    unchanged = models.IntegerField(default=0)
    skipped_reasons = models.JSONField(default=dict)
    skipped_details = models.JSONField(default=list)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"SyncRun({self.ats_source}, {self.status}, {self.started_at})"
