"""
Digital pass QR. The member portal shows a signed, short-lived token
("SGPASS:<signed>") that refreshes every minute, so a screenshot or a shared
photo of someone's pass stops working quickly. Only staff can resolve a token
(Member Lookup), so scanning a pass with a phone camera reveals nothing.
"""
from django.core import signing

PREFIX = 'SGPASS:'
SALT = 'smartgym.member-pass'
MAX_AGE_SECONDS = 120          # the portal refreshes the QR every 60s


class InvalidPass(Exception):
    pass


def make_token(membership):
    return PREFIX + signing.dumps({'m': membership.member_id, 'p': membership.pass_id}, salt=SALT, compress=True)


def read_token(token):
    """Membership for a scanned token. Raises InvalidPass (expired, forged, pass re-issued)."""
    from .models import Membership
    token = (token or '').strip()
    if not token.startswith(PREFIX):
        raise InvalidPass('Not a Smart Gym pass.')
    try:
        data = signing.loads(token[len(PREFIX):], salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.SignatureExpired:
        raise InvalidPass('This pass QR has expired — ask the member to refresh it.')
    except signing.BadSignature:
        raise InvalidPass('This pass QR is not valid.')
    membership = Membership.objects.select_related('member', 'plan').filter(
        member_id=data.get('m'), pass_id=data.get('p')).first()
    if membership is None:
        raise InvalidPass('This pass is no longer valid.')
    return membership
