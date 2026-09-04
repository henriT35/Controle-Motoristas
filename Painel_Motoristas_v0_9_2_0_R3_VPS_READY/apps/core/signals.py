from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.drivers.models import Driver, DriverQualityEvent
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof, ProofRecoverySubmission, ProofRetention, ProofPickupAttempt, ProofPickupOpportunity, ProofRetentionObligation
from .cache import invalidate_operational_cache
from .models import SystemSettings

WATCHED = (
    Driver, CTe, Manifest, DeliveryMovement, DeliveryOccurrence,
    RetainedProof, ProofRecoverySubmission, ProofRetention, ProofPickupAttempt, ProofPickupOpportunity, ProofRetentionObligation,
    DriverQualityEvent, SystemSettings,
)


@receiver(post_save, sender=Driver)
@receiver(post_delete, sender=Driver)
@receiver(post_save, sender=CTe)
@receiver(post_delete, sender=CTe)
@receiver(post_save, sender=Manifest)
@receiver(post_delete, sender=Manifest)
@receiver(post_save, sender=DeliveryMovement)
@receiver(post_delete, sender=DeliveryMovement)
@receiver(post_save, sender=DeliveryOccurrence)
@receiver(post_delete, sender=DeliveryOccurrence)
@receiver(post_save, sender=RetainedProof)
@receiver(post_delete, sender=RetainedProof)
@receiver(post_save, sender=ProofRecoverySubmission)
@receiver(post_delete, sender=ProofRecoverySubmission)
@receiver(post_save, sender=ProofRetention)
@receiver(post_delete, sender=ProofRetention)
@receiver(post_save, sender=ProofPickupAttempt)
@receiver(post_delete, sender=ProofPickupAttempt)
@receiver(post_save, sender=ProofPickupOpportunity)
@receiver(post_delete, sender=ProofPickupOpportunity)
@receiver(post_save, sender=ProofRetentionObligation)
@receiver(post_delete, sender=ProofRetentionObligation)
@receiver(post_save, sender=DriverQualityEvent)
@receiver(post_delete, sender=DriverQualityEvent)
@receiver(post_save, sender=SystemSettings)
@receiver(post_delete, sender=SystemSettings)
def invalidate_after_operational_change(sender, **kwargs):
    invalidate_operational_cache(sender.__name__)
