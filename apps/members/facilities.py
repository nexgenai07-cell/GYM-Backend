"""
Facility add-ons: prices, signup quotes, mid-membership quotes and access.

  signup  : facility.monthly_price x the months chosen for it (1 … membership months)
  add-on  : facility.monthly_price x months remaining (a started month counts as a whole month)
Access ends on the membership expiry date at the time of purchase; there is
no downgrade or refund.
"""
from datetime import date
from decimal import Decimal

from .models import FacilityAddon, Membership, MembershipFacility


class FacilityError(Exception):
    pass


def bookable():
    return (FacilityAddon.objects.select_related('item')
            .filter(is_bookable=True, monthly_price__gt=0, item__collection='facilities', item__is_active=True)
            .order_by('item__order', 'item_id'))


def parse_ids(raw):
    """'3,7' / [3, 7] / '' -> [3, 7] (unique, order kept)."""
    return [i for i, _ in parse_selection(raw, None)]


def parse_selection(raw, plan_months):
    """
    Facilities chosen at signup, each with its own length:
    '3,7' (both for the whole plan) or '3:6,7:1' (3 for 6 months, 7 for 1 month)
    -> [(3, 6), (7, 1)]. A facility can run for the plan's length or less, never longer.
    """
    if raw in (None, ''):
        return []
    parts = raw if isinstance(raw, (list, tuple)) else str(raw).split(',')
    out, seen = [], set()
    for p in parts:
        p = str(p).strip()
        if not p:
            continue
        item, _, months = p.partition(':')
        if not item.isdigit() or (months and not months.isdigit()):
            raise FacilityError('Facilities must be ids, optionally with months ("3:6").')
        m = int(months) if months else plan_months
        if plan_months is not None and not 1 <= m <= plan_months:
            raise FacilityError(f'A facility can last 1 to {plan_months} months (your plan length).')
        if int(item) not in seen:
            seen.add(int(item))
            out.append((int(item), m))
    return out


def signup_quote(selection, months=None):
    """
    Frozen line items for a registration: [{id, name, monthly_price, months, amount}].
    `selection` = [(item_id, months)] (or plain ids, which take `months`).
    """
    if not selection:
        return []
    pairs = [(s, months) if isinstance(s, int) else s for s in selection]
    addons = {a.item_id: a for a in bookable().filter(item_id__in=[i for i, _ in pairs])}
    if any(i not in addons for i, _ in pairs):
        raise FacilityError('One or more selected facilities can’t be booked.')
    return [{
        'id': i,
        'name': addons[i].name,
        'monthly_price': str(addons[i].monthly_price),
        'months': m,
        'amount': str((addons[i].monthly_price * m).quantize(Decimal('0.01'))),
    } for i, m in pairs]


def quote_total(lines):
    return sum((Decimal(line['amount']) for line in lines or []), Decimal('0.00'))


def months_remaining(membership):
    t = membership.time_remaining
    if t['expired']:
        return 0
    return t['months'] + (1 if t['days'] else 0)


def active_ids(member):
    return set(MembershipFacility.objects.filter(member=member, expires_on__gt=date.today())
               .values_list('item_id', flat=True))


def addon_quote(member, item_id):
    """(addon, months, amount) for buying a facility mid-membership. Raises FacilityError."""
    membership = Membership.objects.filter(member=member).first()
    if membership is None or not membership.allows_entry:
        raise FacilityError('You need an active membership to add a facility.')
    addon = bookable().filter(item_id=item_id).first()
    if addon is None:
        raise FacilityError('This facility can’t be booked.')
    if item_id in active_ids(member):
        raise FacilityError('You already have access to this facility.')
    months = months_remaining(membership)
    if months < 1:
        raise FacilityError('Your membership has no time left to add a facility to.')
    return addon, months, (addon.monthly_price * months).quantize(Decimal('0.01'))


def grant(member, item_id, name, monthly_price, months, amount, starts_on, expires_on, source):
    return MembershipFacility.objects.create(
        member=member, item_id=item_id, facility_name=name, monthly_price=monthly_price,
        months=months, amount=amount, starts_on=starts_on, expires_on=expires_on, source=source,
    )


def member_view(member):
    """What the portal shows: every bookable facility with ownership + today's add-on price."""
    membership = Membership.objects.filter(member=member).first()
    months = months_remaining(membership) if membership else 0
    owned = {f.item_id: f for f in MembershipFacility.objects.filter(member=member, expires_on__gt=date.today())}
    rows = []
    for a in bookable():
        f = owned.get(a.item_id)
        rows.append({
            'id': a.item_id,
            'name': a.name,
            'image_url': a.item.image_url,
            'monthly_price': str(a.monthly_price),
            'owned': f is not None,
            'expires_on': f.expires_on.isoformat() if f else None,
            'months_remaining': months,
            'addon_price': str((a.monthly_price * months).quantize(Decimal('0.01'))) if months else None,
        })
    # Access bought earlier for a facility that's no longer offered still shows.
    for item_id, f in owned.items():
        if not any(r['id'] == item_id for r in rows):
            rows.append({'id': item_id, 'name': f.facility_name, 'image_url': '', 'monthly_price': str(f.monthly_price),
                         'owned': True, 'expires_on': f.expires_on.isoformat(), 'months_remaining': months,
                         'addon_price': None})
    return rows
