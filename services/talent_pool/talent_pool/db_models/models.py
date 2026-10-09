from django.db import models


class Candidate(models.Model):
    ats_source = models.CharField(max_length=50)
    external_id = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    phone = models.CharField(max_length=100)
    age = models.IntegerField()
    job_external_id = models.CharField(max_length=255)
    internal_status = models.CharField(max_length=50)
    applied_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ats_source", "external_id"],
                name="unique_ats_source_external_id",
            )
        ]

    def __str__(self) -> str:
        return f"{self.ats_source}:{self.external_id}"


class OutboxEvent(models.Model):
    event_id = models.UUIDField(unique=True)
    topic = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.topic}:{self.event_id}"
