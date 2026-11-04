"""Generates authentic, multi-page IRDAI-compliant Health Policy & CIS PDFs for testing and offline runs.

Creates standard Arogya Sanjeevani Policy & Saral Suraksha Bima wordings with all 9 IRDAI sections:
Customer Information Sheet (CIS), Benefit Schedule table, Definitions (Def. 1-25),
Base Coverage (In-patient, Day Care, AYUSH, Modern Treatments, Cumulative Bonus),
Waiting Periods (Excl01 PED, Excl02 Specified Diseases, Excl03 30-day initial),
Permanent Exclusions (Excl04-Excl18), Cost Sharing (Room Rent 1% proportionate deduction, 5% co-pay),
and Claims / Ombudsman grievance procedures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf


def create_arogya_sanjeevani_pdf(output_path: Path) -> Path:
    """Generate a realistic 6-page Arogya Sanjeevani standard health policy PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc: Any = pymupdf.open()

    # -------------------------------- Page 1: CIS Summary
    page1: Any = doc.new_page(width=595, height=842)
    p1_text = """AROGYA SANJEEVANI POLICY, NATIONAL INSURANCE CO. LTD.
STANDARD HEALTH INSURANCE POLICY WORDINGS (IRDAI UIN: NICHLIP20177V011920)

CUSTOMER INFORMATION SHEET (CIS) - KEY FEATURES
The Customer Information Sheet provides a summary of key product features.
Please refer to the Policy Document for complete terms, conditions, and exclusions.

1. Product Name: Arogya Sanjeevani Policy, National Insurance Co. Ltd.
2. Sum Insured Options: ₹1,00,000 to ₹5,00,000 in multiples of ₹50,000.
3. In-Patient Hospitalization: Covered up to Sum Insured for room rent, nursing, ICU, surgeon, and diagnostic tests.
4. Room Rent Sub-limit: Up to 2% of Sum Insured subject to maximum ₹5,000 per day. ICU charges up to 5% of Sum Insured subject to maximum ₹10,000 per day. Proportionate deduction applies if higher room category is chosen.
5. Cataract Treatment Limit: Up to 25% of Sum Insured or ₹40,000 per eye, whichever is lower.
6. Co-Payment: A mandatory co-payment of 5% applies to each and every admissible claim.
7. Pre-Hospitalization & Post-Hospitalization: 30 days pre-hospitalization and 60 days post-hospitalization medical expenses.
8. AYUSH Treatment: In-patient hospitalization under Ayurveda, Yoga and Naturopathy, Unani, Siddha, and Homeopathy systems covered up to 100% of Sum Insured in government-recognized AYUSH hospitals.
9. Cumulative Bonus: 5% increase in Sum Insured for each claim-free year up to a maximum of 50%.
10. Waiting Periods: Initial 30 days (Excl03), 24 months for specified diseases (Excl02), and 48 months for Pre-Existing Diseases (Excl01).
"""
    page1.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p1_text, fontsize=9.5, fontname="helv", lineheight=1.4
    )

    # -------------------------------- Page 2: Schedule of Benefits (with Table)
    page2: Any = doc.new_page(width=595, height=842)
    p2_head = """SECTION 1: SCHEDULE OF BENEFITS
TABLE OF BENEFITS AND SUB-LIMITS APPLICABLE ACROSS PLAN VARIANTS

The following schedule sets forth the maximum limits of indemnity payable under the policy."""
    page2.insert_textbox(
        pymupdf.Rect(50, 60, 545, 125), p2_head, fontsize=10, fontname="helv", lineheight=1.4
    )

    # Draw tabular grid on page 2
    table_rect = pymupdf.Rect(50, 130, 545, 320)
    page2.draw_rect(table_rect, color=(0.1, 0.3, 0.7), width=1.2)
    headers = ["Benefit Category", "₹2,00,000 SI", "₹3,50,000 SI", "₹5,00,000 SI"]
    col_x = [50, 200, 315, 430, 545]
    row_y = [130, 160, 190, 220, 250, 280, 310]

    # Header fill
    page2.draw_rect(pymupdf.Rect(50, 130, 545, 160), color=(0.1, 0.3, 0.7), fill=(0.9, 0.93, 0.98))
    for i, h in enumerate(headers):
        page2.insert_text(
            (col_x[i] + 5, 150), h, fontsize=9, fontname="helv", color=(0.05, 0.15, 0.4)
        )

    rows_data = [
        ["Room Rent / Day", "₹4,000 (2% SI)", "₹5,000 (Max)", "₹5,000 (Max)"],
        ["ICU Charges / Day", "₹10,00,000 (5% SI)", "₹10,000 (Max)", "₹10,000 (Max)"],
        ["Cataract per Eye", "₹40,000 (Max)", "₹40,000 (Max)", "₹40,000 (Max)"],
        ["Modern Treatments", "50% of SI", "50% of SI", "50% of SI"],
        ["Mandatory Co-Pay", "5% each claim", "5% each claim", "5% each claim"],
    ]
    for r_idx, row in enumerate(rows_data):
        y_top = row_y[r_idx + 1]
        page2.draw_line(
            pymupdf.Point(50, y_top), pymupdf.Point(545, y_top), color=(0.8, 0.8, 0.8), width=0.8
        )
        for c_idx, cell in enumerate(row):
            page2.insert_text((col_x[c_idx] + 5, y_top + 18), cell, fontsize=8.5, fontname="helv")

    for x in col_x[1:-1]:
        page2.draw_line(
            pymupdf.Point(x, 130), pymupdf.Point(x, 310), color=(0.8, 0.8, 0.8), width=0.8
        )

    footnotes = """* Note: Proportionate deduction applies to associate medical expenses if room category higher than eligibility is opted.
** Modern Treatments include robotic surgeries, balloon sinuplasty, immunotherapy, deep brain stimulation, and stem cell therapy."""
    page2.insert_textbox(
        pymupdf.Rect(50, 335, 545, 450),
        footnotes,
        fontsize=8,
        fontname="helv",
        color=(0.3, 0.3, 0.3),
    )

    # -------------------------------- Page 3: Definitions
    page3: Any = doc.new_page(width=595, height=842)
    p3_text = """SECTION 2: STANDARD DEFINITIONS (IRDAI STANDARDIZED TERMS)

2.1 Accident: An accident means sudden, unforeseen and involuntary event caused by external, violent and visible means.
2.2 AYUSH Hospital: An AYUSH Hospital is a healthcare facility wherein medical/surgical/para-surgical treatment procedures and interventions are carried out by AYUSH Medical Practitioners in recognized Ayurveda, Yoga & Naturopathy, Unani, Siddha or Homeopathy disciplines.
2.3 Cashless Facility: A facility extended by the Insurer to the Insured where the payments of the costs of treatment undergone by the Insured in accordance with the policy terms are directly made to the Network Provider by the Insurer.
2.4 Co-Payment: A cost sharing requirement under a health insurance policy that provides that the policyholder/insured will bear a specified percentage of the admissible claim amount. A co-payment does not reduce the Sum Insured.
2.5 Cumulative Bonus: Any increase in the Sum Insured granted by the insurer without an associated increase in premium.
2.6 Day Care Treatment: Medical treatment and/or surgical procedure which is undertaken under General or Local Anesthesia in a hospital/day care centre in less than 24 hours because of technological advancement.
2.7 Deductible: A cost sharing requirement that provides that the insurer will not be liable for a specified rupee amount in respect of medical expenses incurred before insurance coverage applies.
2.8 Network Provider: Hospitals enlisted by an insurer, TPA or jointly by an insurer and TPA to provide medical services to an insured by a cashless facility.
2.9 Pre-Existing Disease (PED): Pre-existing disease means any condition, ailment, injury or disease that is diagnosed by a physician within 48 months prior to the effective date of the policy issued by the insurer or for which medical advice or treatment was recommended by, or received from, a physician within 48 months prior to the effective date of the policy.
2.10 Proportionate Deduction: If the Insured occupies a room category higher than the eligible room category, the associated medical expenses (excluding medicine, implants, and consumables) shall be paid in the proportion of eligible room rent to actual room rent incurred.
"""
    page3.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p3_text, fontsize=9, fontname="helv", lineheight=1.4
    )

    # -------------------------------- Page 4: Base Coverage & Optional Riders
    page4: Any = doc.new_page(width=595, height=842)
    p4_text = """SECTION 3: BASE COVERAGE (WHAT IS COVERED)

3.1 In-Patient Hospitalization:
The company shall indemnify medical expenses incurred in respect of the Insured Person for:
a. Room Rent, Boarding and Nursing Expenses as provided by the Hospital/Nursing Home up to 2% of Sum Insured or ₹5,000 per day.
b. Intensive Care Unit (ICU) / Intensive Cardiac Care Unit (ICCU) expenses up to 5% of Sum Insured or ₹10,000 per day.
c. Surgeon, Anesthetist, Medical Practitioner, Consultants, Specialists Fees.
d. Anesthesia, Blood, Oxygen, Operation Theatre Charges, surgical appliances, Medicines & Drugs, Diagnostic lab & X-ray.

3.2 Day Care Procedures:
Coverage extends to all day care treatments and surgical procedures requiring less than 24 hours hospitalization due to technological advancement. Outpatient treatment is not covered.

3.3 AYUSH In-Patient Hospitalization:
Expenses incurred for In-patient hospitalization treatment under Ayurveda, Yoga and Naturopathy, Unani, Siddha and Homeopathy systems of medicines shall be covered up to 100% of Sum Insured in government recognized AYUSH hospital.

3.4 Modern Treatment Methods:
The following advanced procedures are covered up to 50% of Sum Insured: Uterine Artery Embolization, Balloon Sinuplasty, Deep Brain Stimulation, Oral Chemotherapy, Immunotherapy, Robotic Surgeries, Stereotactic Radio Surgeries, Bronchial Thermoplasty, and Intra-vitreal injections.

3.5 Road Ambulance Charges:
Expenses incurred on road ambulance services for transportation to hospital up to ₹2,000 per hospitalization.

SECTION 4: OPTIONAL RIDERS & ADD-ON COVERS
4.1 Hospital Daily Cash Benefit:
Optional rider providing a daily allowance of ₹1,000 per day for each continuous 24 hours of hospitalization, up to a maximum of 30 days per policy year.
"""
    page4.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p4_text, fontsize=9, fontname="helv", lineheight=1.4
    )

    # -------------------------------- Page 5: Waiting Periods & Permanent Exclusions
    page5: Any = doc.new_page(width=595, height=842)
    p5_text = """SECTION 5: WAITING PERIODS (EXCLUSIONS APPLICABLE FOR SPECIFIC TIME)

5.1 Pre-Existing Diseases (Code-Excl01):
a. Expenses related to the treatment of a Pre-Existing Disease (PED) and its direct complications shall be excluded until the expiry of 48 months of continuous coverage after the date of inception of the first policy with us.
b. In case of enhancement of Sum Insured, the 48-month exclusion shall apply afresh to the enhanced portion.

5.2 Specified disease/procedure waiting period (Code-Excl02):
a. Expenses related to the treatment of the listed Conditions, surgeries/treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception:
1. Benign ENT disorders, Tonsillectomy, Adenoidectomy, Mastoidectomy.
2. Cataract and benign prostatic hypertrophy.
3. Hysterectomy for menorrhagia or fibromyoma.
4. Hernia, Hydrocele, Fistula in anus, Piles, Sinusitis, Calculus diseases of gall bladder and urogenital system.
5. Osteoarthritis, Gout and Rheumatism, Joint replacement surgery unless arising from accident.

5.3 30-day initial waiting period (Code-Excl03):
a. Expenses related to the treatment of any illness within 30 days from the first policy commencement date shall be excluded except claims arising from an accident.

SECTION 6: PERMANENT EXCLUSIONS (CODE-Excl04 TO Excl18)
The Company shall not be liable to make any payment under this policy in respect of:
6.1 Code-Excl04 (Investigation & Evaluation): Expenses related to diagnostic evaluation only.
6.2 Code-Excl05 (Rest Cure, rehabilitation and respite care).
6.3 Code-Excl06 (Obesity/ Weight Control): Expenses associated with surgical treatment of obesity.
6.4 Code-Excl07 (Change-of-Gender treatments).
6.5 Code-Excl08 (Cosmetic or plastic Surgery): Surgeries for beautification or cosmetic appearance.
6.6 Code-Excl09 (Hazardous or Adventure sports).
6.7 Code-Excl10 (Breach of law): Expenses incurred for treatment directly arising from breach of law.
6.8 Code-Excl12 (Alcoholism, drug or substance abuse).
6.9 Code-Excl16 (Unproven Treatments): Any treatment or surgery not recognized by modern medicine.
6.10 Code-Excl17 (Sterility and Infertility): Assisted reproductive services and IVF.
6.11 Code-Excl18 (Maternity): Medical treatment expenses traceable to childbirth or pregnancy.
"""
    page5.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p5_text, fontsize=8.8, fontname="helv", lineheight=1.35
    )

    # -------------------------------- Page 6: Cost Sharing & Claims / Grievance
    page6: Any = doc.new_page(width=595, height=842)
    p6_text = """SECTION 7: COST SHARING & CO-PAYMENT CONDITIONS

7.1 Mandatory Co-Payment:
Every admissible claim under this policy shall be subject to a co-payment of 5% on the admissible claim amount. The co-payment shall be borne by the Insured Person.

7.2 Room Rent Proportionate Deduction:
In case of admission to a room category exceeding the eligible limit (2% of Sum Insured up to ₹5,000 per day), the Insurer shall proportionately reduce all associated medical expenses (including doctor consultation, surgical charges, nursing and OT) in the ratio of eligible room rent to actual room rent charged.

SECTION 8: CLAIMS PROCEDURE & GRIEVANCE REDRESSAL

8.1 Cashless Claims Procedure:
For planned hospitalization, the insured person must submit cashless pre-authorization request at least 48 hours prior to admission. For emergency hospitalization, notice must be given within 24 hours of hospital admission.

8.2 Reimbursement Claims Procedure:
Notice of claim must be given within 24 hours of admission. Duly completed claim form along with original bills, discharge summary, diagnostic reports and payment receipts must be submitted within 30 days from discharge.

8.3 Grievance Redressal Mechanism & Insurance Ombudsman:
If the Insured is not satisfied with the grievance resolution by the Company within 15 days, they may approach the Insurance Ombudsman appointed under the Insurance Ombudsman Rules, 2017. Policyholders may also lodge complaints on the IRDAI Bima Bharosa portal (bimabharosa.irdai.gov.in) or call toll-free 155255.
"""
    page6.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p6_text, fontsize=9, fontname="helv", lineheight=1.4
    )

    doc.save(str(output_path))
    doc.close()
    return output_path


def create_saral_suraksha_bima_pdf(output_path: Path) -> Path:
    """Generate a realistic 3-page Saral Suraksha Bima (Standard Personal Accident) policy PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc: Any = pymupdf.open()

    page1: Any = doc.new_page(width=595, height=842)
    p1 = """SARAL SURAKSHA BIMA, HDFC ERGO GENERAL INSURANCE COMPANY
STANDARD ACCIDENTAL INSURANCE POLICY (IRDAI UIN: HDFPAIP21175V012021)

CUSTOMER INFORMATION SHEET (CIS) & SUMMARY OF BENEFITS
1. Product Name: Saral Suraksha Bima, HDFC ERGO General Insurance Co. Ltd.
2. Sum Insured Options: ₹2,50,000 to ₹1,00,00,000.
3. Death Benefit: 100% of Sum Insured payable upon accidental death within 12 calendar months of injury.
4. Permanent Total Disablement (PTD): 100% of Sum Insured payable for loss of two limbs or complete blindness.
5. Permanent Partial Disablement (PPD): Up to 50% of Sum Insured as per specified benefit table.
6. Temporary Total Disablement (TTD): 0.2% of Sum Insured per week up to ₹10,000 per week for 100 weeks.
"""
    page1.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p1, fontsize=9.5, fontname="helv", lineheight=1.4
    )

    page2: Any = doc.new_page(width=595, height=842)
    p2 = """SECTION 1: BASE COVERAGE (SCOPE OF COVER)
1.1 Accidental Death Cover: 100% Sum Insured on accidental demise within 12 months.
1.2 Permanent Total Disablement: Loss of both hands, loss of both feet, complete and irrecoverable loss of sight.

SECTION 2: DEFINITIONS
2.1 Accident: Sudden, unforeseen, and involuntary event caused by external, violent, visible means.
2.2 Injury: Accidental bodily injury caused solely and directly by external, violent, visible means.

SECTION 3: PERMANENT EXCLUSIONS
1. Suicide, attempted suicide, or self-inflicted injuries.
2. War, invasion, act of foreign enemy, hostilities, or civil war.
3. Participation in hazardous or adventure sports without prior written underwriting approval.
4. Injuries sustained under the influence of intoxicating liquor or drugs.
"""
    page2.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p2, fontsize=9.5, fontname="helv", lineheight=1.4
    )

    page3: Any = doc.new_page(width=595, height=842)
    p3 = """SECTION 4: CLAIMS PROCEDURE & OMBUDSMAN REDRESSAL
Written notice of claim must be given within 30 days of death or injury.
Submit completed claim form, death certificate, police FIR, post-mortem report, and identity proof.
If unresolved, complaints may be escalated to the Insurance Ombudsman under IRDAI guidelines.
"""
    page3.insert_textbox(
        pymupdf.Rect(50, 60, 545, 800), p3, fontsize=9.5, fontname="helv", lineheight=1.4
    )

    doc.save(str(output_path))
    doc.close()
    return output_path
