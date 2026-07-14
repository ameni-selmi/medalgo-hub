"""
Delete uploaded inference run files older than 24 hours (keeps metadata).

    python manage.py cleanup_old_runs
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from algorithms.models import InferenceRun


class Command(BaseCommand):
    help = "Delete inference run input/output files older than 24 hours."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        old_runs = InferenceRun.objects.filter(created_at__lt=cutoff)
        count = 0
        for run in old_runs:
            if run.input_image:
                try:
                    run.input_image.delete(save=False)
                except Exception:
                    pass
            if run.gradcam_image:
                try:
                    run.gradcam_image.delete(save=False)
                except Exception:
                    pass
            run.input_image = ""
            run.gradcam_image = ""
            run.save(update_fields=["input_image", "gradcam_image"])
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Cleaned up {count} old runs."))
