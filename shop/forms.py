import re
from django import forms


class CheckoutForm(forms.Form):
    name = forms.CharField(max_length=100, min_length=3)
    phone = forms.CharField(max_length=20)
    address = forms.CharField(min_length=10)

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_phone(self):
        phone = re.sub(r'[\s\-]', '', self.cleaned_data['phone'])
        if not re.match(r'^(\+92|0)3\d{9}$', phone):
            raise forms.ValidationError('Sahi number likhein, jaise 03001234567')
        return phone

    def clean_address(self):
        return self.cleaned_data['address'].strip()