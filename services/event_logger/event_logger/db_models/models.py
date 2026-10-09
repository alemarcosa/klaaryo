from django.db import models


class ProcessedEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    candidate_pk = models.IntegerField()
    ats_source = models.CharField(max_length=50)
    received_at = models.DateTimeField(auto_now_add=True)
    payload_json = models.TextField()

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.event_id}"
