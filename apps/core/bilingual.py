"""English · Arabic labels for CSV headers and other documents (one column header carries both)."""

AR = {
    'Date': 'التاريخ', 'Date (gym time)': 'التاريخ (توقيت النادي)', 'Transaction': 'رقم العملية', 'Member': 'العضو',
    'Email': 'البريد الإلكتروني', 'Item': 'البند', 'Description': 'الوصف', 'Type': 'النوع', 'Paid with': 'طريقة الدفع',
    'Amount (SAR)': 'المبلغ (ريال)', 'Status': 'الحالة', 'Month': 'الشهر', 'VAT included (SAR)': 'ضريبة القيمة المضافة (ريال)',
    'Total (SAR)': 'الإجمالي (ريال)', 'Name': 'الاسم', 'Phone': 'الجوال', 'Iqama': 'الإقامة', 'Plan': 'الخطة',
    'Membership': 'العضوية', 'Started': 'البداية', 'Expires': 'الانتهاء', 'Account created': 'تاريخ إنشاء الحساب',
    'Joined in period': 'انضم خلال الفترة', 'Account active': 'الحساب نشط', 'Joined': 'تاريخ الانضمام',
    'Checked in': 'وقت الدخول', 'Checked out': 'وقت الخروج', 'Minutes': 'الدقائق', 'Zone': 'المنطقة',
    'Machine': 'الجهاز', 'Category': 'الفئة', 'QR code': 'رمز QR', 'In service': 'في الخدمة', 'Times used': 'مرات الاستخدام',
    'Sets logged': 'المجموعات المسجلة', 'Members': 'الأعضاء', 'Trainer': 'المدرب', 'Title': 'المسمى',
    '1:1 completed': 'جلسات فردية مكتملة', '1:1 upcoming': 'جلسات فردية قادمة', '1:1 cancelled': 'جلسات فردية ملغاة',
    'No-shows': 'عدم الحضور', '1:1 sales (SAR)': 'مبيعات الجلسات الفردية (ريال)', 'Course enrolments': 'التسجيلات في الدورات',
    'Course sales (SAR)': 'مبيعات الدورات (ريال)', 'Rating': 'التقييم', 'Total received': 'إجمالي المستلم', 'Total': 'الإجمالي',
    'Memberships & add-ons': 'العضويات والإضافات', 'Shop': 'المتجر', 'Trainers & courses': 'المدربون والدورات',
    'Locker credit top-ups': 'شحن رصيد الخزانة', 'Refunds': 'المبالغ المستردة', 'Subscription': 'اشتراك', 'Retail': 'المتجر',
    'Coaching': 'تدريب', 'Top-up': 'شحن رصيد', 'Refund': 'استرداد', 'yes': 'نعم', 'no': 'لا',
    'Counted as revenue': 'محتسب كإيراد',
}


def label(en):
    """'Date' → 'Date · التاريخ' (unknown labels stay English)."""
    ar = AR.get(en)
    if ar is None and en.endswith(' (SAR)'):
        base = AR.get(en[:-6])
        ar = f'{base} (ريال)' if base else None
    return f'{en} · {ar}' if ar else en


def header(cols):
    return [label(c) for c in cols]
