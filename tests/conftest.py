import pytest


@pytest.fixture
def sample_raw_text_receipt():
    return """BIG BAZAAR
MG Road, Bangalore
Date: 15/01/2024
Bill No: B-12345

Item          Qty   MRP    Amount
Rice 5kg      1    450.00  450.00
Dal 1kg       2    120.00  240.00
Oil 1L        1    180.00  180.00

Subtotal:                   870.00
CGST 2.5%:                   21.75
SGST 2.5%:                   21.75
Grand Total:                913.50

Payment: UPI
Thank you for shopping!"""


@pytest.fixture
def sample_raw_text_invoice():
    return """TAX INVOICE
Invoice No: INV-2024-001
Date: 15/01/2024
Due Date: 15/02/2024

From: ABC Corp
GSTIN: 29ABCDE1234F1Z5

Bill To: XYZ Ltd

Description         Qty   Rate    Amount
Consulting          10    1000    10000.00

Subtotal:                       10000.00
IGST 18%:                        1800.00
Total:                          11800.00"""


@pytest.fixture
def sample_raw_text_driving_license():
    return """UNION OF INDIA
DRIVING LICENCE
DL No: KA01 20190001234
Name: RAJESH KUMAR
S/O: SURESH KUMAR
DOB: 15/05/1990
Address: 123, MG Road, Bangalore
Blood Group: B+
Date of Issue: 10/01/2019
Valid Till: 09/01/2039
Class of Vehicle: MCWG, LMV
RTO: KA01 - Bangalore"""


@pytest.fixture
def sample_raw_text_rc_book():
    return """REGISTRATION CERTIFICATE
Registration No: KA01AB1234
Owner: RAJESH KUMAR
S/O: SURESH KUMAR
Address: 123, MG Road, Bangalore
Vehicle Make: MARUTI SUZUKI
Model: SWIFT DZIRE
Vehicle Type: Sedan
Fuel Type: Petrol
Engine No: K12M1234567
Chassis No: MA3FJEB1S00123456
Date of Registration: 15/03/2020
Valid Till: 14/03/2035
Seating Capacity: 5
Colour: White
RTO: KA01 - Bangalore"""


@pytest.fixture
def sample_raw_text_insurance():
    return """MOTOR INSURANCE POLICY
Policy No: POL-2024-12345678
Insurer: ICICI LOMBARD
Insured: RAJESH KUMAR
Vehicle No: KA01AB1234
Vehicle: MARUTI SWIFT DZIRE
Policy Type: Comprehensive
Effective From: 01/01/2024
Effective To: 01/01/2025
Premium: Rs.8500.00
IDV: Rs.450000
Nominee: SUNITA KUMAR
Cover: Third Party + Own Damage"""


@pytest.fixture
def sample_raw_text_petrol_receipt():
    return """HP PETROL PUMP
MG Road, Bangalore
Date: 15/01/2024
Time: 14:30:00
Bill No: TXN-123456

Fuel: PETROL
Quantity: 25.50 Litres
Rate: Rs.102.50/Ltr
Total Amount: Rs.2613.75

Vehicle No: KA01AB1234
Nozzle: 3
Payment: Card"""


@pytest.fixture
def sample_raw_text_odometer():
    return """ODOMETER READING
Vehicle: KA01AB1234
Date: 15/01/2024
Reading: 45230 KM"""


@pytest.fixture
def sample_raw_text_fuel_pump():
    return """FUEL PUMP READING
Pump No: 3
Fuel: PETROL
Date: 15/01/2024
Opening Reading: 123456.78
Closing Reading: 123482.28
Quantity Dispensed: 25.50 Litres"""
