"""
Shared field rules for every form (portal, admin console, public website): email, names,
short codes. Each helper returns an error message (English) or None, so views can put it
straight into their {field: message} error dict.
"""
import re

EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$')
EMAIL_MESSAGE = 'Enter a valid email address, e.g. name@example.com.'


def email_error(value, required=True):
    """None when `value` is a usable email address."""
    v = str(value or '').strip()
    if not v:
        return 'Email is required.' if required else None
    if len(v) > 254:
        return 'Email is too long (254 characters max).'
    local = v.split('@', 1)[0]
    if not EMAIL_RE.match(v) or '..' in v or local.startswith('.') or local.endswith('.') or len(local) > 64:
        return EMAIL_MESSAGE
    return None


NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\-.][^\W\d_]+)*\.?$", re.UNICODE)   # letters (any script), spaces, ' - .


def person_name_error(value, label='Name', required=True, max_length=150):
    """Letters only (Arabic or Latin), with spaces, apostrophes, hyphens or dots between words."""
    v = ' '.join(str(value or '').split())
    if not v:
        return f'{label} is required.' if required else None
    if len(v) > max_length:
        return f'{label} must be {max_length} characters or fewer.'
    if not NAME_RE.match(v):
        return f'{label} can only contain letters, spaces, apostrophes and hyphens.'
    return None


def norm(value):
    """Case- and space-insensitive form used for duplicate checks ("  Pro  Plan" == "pro plan")."""
    return ' '.join(str(value or '').split()).casefold()


def duplicate_error(qs, field, value, label, exclude_id=None):
    """'<label> “x” already exists.' when another row of `qs` has the same `field` (ignoring case/spaces)."""
    v = ' '.join(str(value or '').split())
    if not v:
        return None
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    for other in qs.filter(**{f'{field}__iexact': v}).values_list(field, flat=True)[:1]:
        return f'{label} “{other}” already exists. Choose a different one.'
    # catch differences in inner spacing too ("Pro  Plan")
    first = v.split(' ')[0]
    for other in qs.filter(**{f'{field}__icontains': first}).values_list(field, flat=True)[:200]:
        if norm(other) == norm(v):
            return f'{label} “{other}” already exists. Choose a different one.'
    return None


def code_error(value, pattern, example, label, required=True):
    """Short codes with a fixed format (SKU, room, asset id...)."""
    v = str(value or '').strip()
    if not v:
        return f'{label} is required.' if required else None
    if not re.fullmatch(pattern, v):
        return f'{label} must look like {example}.'
    return None


def apply_person_fields(user, data, errors, name_required=True):
    """
    Copies first_name / last_name / phone from `data` onto `user` (not saved), with the shared
    rules: letters-only names, Saudi mobile numbers (stored as +9665XXXXXXXX). Errors go in `errors`.
    """
    from apps.core.phone import MESSAGE as PHONE_MESSAGE, normalize_saudi_mobile
    for field, label, required in (('first_name', 'First name', name_required), ('last_name', 'Last name', False)):
        if field in data:
            value = ' '.join(str(data.get(field) or '').split())
            msg = person_name_error(value, label, required=required)
            if msg:
                errors[field] = msg
            setattr(user, field, value)
    if 'phone' in data:
        raw = str(data.get('phone') or '').strip()
        if not raw:
            user.phone = ''
        else:
            phone = normalize_saudi_mobile(raw)
            if phone is None:
                errors['phone'] = PHONE_MESSAGE
            user.phone = phone or raw
