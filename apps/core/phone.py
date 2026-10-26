"""Saudi mobile numbers: 05XXXXXXXX, 5XXXXXXXX, +9665XXXXXXXX or 009665XXXXXXXX → +9665XXXXXXXX."""
import re

_DIGITS = re.compile(r'\D')
MESSAGE = 'Enter a Saudi mobile number, e.g. 05XXXXXXXX.'
MESSAGE_AR = 'أدخل رقم جوال سعودي، مثل 05XXXXXXXX.'


def normalize_saudi_mobile(value):
    """Returns +9665XXXXXXXX, or None when it isn't a Saudi mobile number."""
    d = _DIGITS.sub('', str(value or ''))
    if d.startswith('00966'):
        d = d[5:]
    elif d.startswith('966'):
        d = d[3:]
    if d.startswith('0'):
        d = d[1:]
    if len(d) == 9 and d.startswith('5'):
        return f'+966{d}'
    return None
