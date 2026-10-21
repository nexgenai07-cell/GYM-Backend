"""
Members approved before this release paid at signup, but that payment never
reached their ledger. Add a settled Transaction + paid Invoice for each one
(skipped when one with the same Moyasar reference already exists).
"""
import uuid

from django.db import migrations


def forward(apps, schema_editor):
    Registration = apps.get_model('members', 'MembershipRegistration')
    Transaction = apps.get_model('payments', 'Transaction')
    Invoice = apps.get_model('payments', 'Invoice')
    regs = Registration.objects.filter(status='approved', payment_status='paid',
                                       created_user__isnull=False).select_related('plan')
    for reg in regs:
        ref = reg.moyasar_payment_id or reg.payment_reference
        if not ref or Transaction.objects.filter(member_id=reg.created_user_id, gateway_reference=ref).exists():
            continue
        when = reg.payment_paid_at or reg.approved_at
        desc = f'Membership — {reg.plan.display_name} ({reg.duration_months} mo)'
        txn = Transaction.objects.create(
            member_id=reg.created_user_id, transaction_id=f'TXN-{uuid.uuid4().hex[:10].upper()}',
            description=desc[:200], transaction_type='subscription', amount=reg.payment_amount,
            subtotal=reg.payment_amount, status='settled',
            payment_method_label=(reg.payment_method or 'card').upper()[:60],
            gateway_reference=ref[:100], settled_at=when,
        )
        Invoice.objects.create(
            invoice_number=f'INV-{uuid.uuid4().hex[:10].upper()}', member_id=reg.created_user_id,
            transaction=txn, description=desc[:200], amount=reg.payment_amount,
            total=reg.payment_amount, status='paid', paid_at=when,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_paymentintent'),
        ('members', '0010_plan_arabic_and_open_codes'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
