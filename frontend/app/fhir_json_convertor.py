from datetime import datetime, timedelta
import pandas as pd

'''
This code copies the Json_to_CSV data processing steps.
'''
def parse_date(date_str):
    """
    Helper function to parse FHIR date strings.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        return None


def get_age_bucket(age):
    """Categorize age into UCI format [0-10), [10-20), etc."""
    if age is None:
        return 'Unknown'
    lower = (age // 10) * 10
    upper = lower + 10
    return f"[{lower}-{upper})"


def is_diabetes_medication(med_name_or_code):
    """
    Diabetes medication checker.
    """
    if not med_name_or_code:
        return False
    med_str = str(med_name_or_code).lower()

    # current list of diabetes medication
    diabetes_drugs = ['insulin', 'metformin', 'glipizide', 'glyburide', 'pioglitazone',
                      'rosiglitazone', 'glimepiride', 'sitagliptin', 'liraglutide',
                      'empagliflozin', 'dapagliflozin']

    return any(drug in med_str for drug in diabetes_drugs)


def extract_features(bundle_data):
    """
    Feature extraction for diabetes dataset.
    """

    patient_id = None
    birth_date = None
    gender = None
    race = 'Unknown'

    # Extract Demographics
    for entry in bundle_data.get('entry', []):
        res = entry.get('resource', {})
        if res.get('resourceType') == 'Patient':
            patient_id = res.get('id')
            birth_date = parse_date(res.get('birthDate'))
            gender = res.get('gender')

            # Extract Race
            for ext in res.get('extension', []):
                if 'us-core-race' in ext.get('url', ''):
                    for sub_ext in ext.get('extension', []):
                        if sub_ext.get('url') == 'text':
                            race = sub_ext.get('valueString')
            break

    # Extract Encounters
    encounters = []
    for entry in bundle_data.get('entry', []):
        res = entry.get('resource', {})
        if res.get('resourceType') == 'Encounter':
            start_dt = parse_date(res.get('period', {}).get('start'))
            end_dt = parse_date(res.get('period', {}).get('end'))
            enc_class = res.get('class', {}).get('code')
            if start_dt:
                # assign start_dt to end_dt if end_dt is missing
                if end_dt is None:
                    final_end = start_dt
                else:
                    final_end = end_dt

                encounters.append({
                    'start': start_dt,
                    'end': final_end,
                    'class': enc_class
                })

    # Sort the encounter
    encounters.sort(key=lambda x: x['start'])

    # Find the first inpatient
    index_admission = None
    for enc in encounters:
        if enc['class'] == 'IMP':
            index_admission = enc
            break

    if not index_admission:
        return None

    index_start = index_admission['start']
    index_end = index_admission['end']

    # Calculate the 365-day lookback window
    lookback_start = index_start - timedelta(days=365)

    # Derive target variable: Readmission in 30 days
    readmitted = 0
    for enc in encounters:
        # Check for another inpatient admission after the index discharge
        if enc['class'] == 'IMP' and enc['start'] > index_end:
            days_to_readmission = (enc['start'] - index_end).days
            if 0 < days_to_readmission <= 30:
                readmitted = 1
                break

    # Derive age group feature
    raw_age = (index_start.year - birth_date.year) if birth_date else None
    age_group = get_age_bucket(raw_age)

    # Derive time_in_hospital (same day stay is consider 1 day)
    time_in_hospital = max((index_end - index_start).days, 1)

    # Baseline (-365 days) Visits
    num_outpatient = 0
    num_emergency = 0
    num_inpatient = 0

    for enc in encounters:
        # Only count visits that occurred in the year prior to the index admission
        if lookback_start <= enc['start'] and enc['end'] < index_start:
            if enc['class'] == 'AMB':
                num_outpatient += 1
            elif enc['class'] == 'EMER':
                num_emergency += 1
            elif enc['class'] == 'IMP':
                num_inpatient += 1

    # Clinical Features (During Index Admission + Historical Diagnoses)
    num_diagnoses = 0
    num_meds = 0
    num_lab_procedures = 0
    num_procedures = 0
    diabetes_med = 'No'
    a1c_result = 'None'

    for entry in bundle_data.get('entry', []):
        res = entry.get('resource', {})
        res_type = res.get('resourceType')

        if res_type == 'Condition':
            # Count diagnoses active or recorded up to the end of the index admission
            dt = parse_date(res.get('onsetDateTime') or res.get('recordedDate'))
            if dt and lookback_start <= dt <= index_end:
                num_diagnoses += 1

        elif res_type == 'MedicationRequest':
            # Medications requested during the index admission
            dt = parse_date(res.get('authoredOn'))
            if dt and index_start <= dt <= index_end:
                num_meds += 1
                med_text = res.get('medicationCodeableConcept', {}).get('text', '')
                if is_diabetes_medication(med_text):
                    diabetes_med = 'Yes'

        elif res_type == 'Observation':
            # Lab results during the index admission
            dt = parse_date(res.get('effectiveDateTime') or res.get('issued'))
            if dt and index_start <= dt <= index_end:
                num_lab_procedures += 1

                # Check for A1C readings
                code_txt = str(res.get('code', {}).get('text', '')).lower()
                if 'hba1c' in code_txt or 'hemoglobin a1c' in code_txt:
                    val = res.get('valueQuantity', {}).get('value')
                    if val:
                        if val > 8:
                            a1c_result = '>8'
                        elif val >= 7:
                            a1c_result = '7'
                        else:
                            a1c_result = 'Norm'

        elif res_type == 'Procedure':
            # Procedures performed DURING the index admission
            period = res.get('performedPeriod', {})
            dt = parse_date(period.get('start') or period.get('end'))
            if dt and index_start <= dt <= index_end:
                num_procedures += 1

    return {
        'patient_id': patient_id,
        'age': age_group,
        'gender': gender,
        'race': race,
        'time_in_hospital': time_in_hospital,
        'num_lab_procedures': num_lab_procedures,
        'num_procedures': num_procedures,
        'num_medications': num_meds,
        'number_outpatient': num_outpatient,
        'number_emergency': num_emergency,
        'number_inpatient': num_inpatient,
        'number_diagnoses': num_diagnoses,
        'diabetesMed': diabetes_med,
        'A1Cresult': a1c_result,
        'admission_type_id': 'Unknown',
        'discharge_disposition_id': 'Unknown',
        'admission_source_id': 'Unknown',
        'readmitted_within_30_days': readmitted
    }

'''
This is the only difference. It converts the webpage added json file
to the Postgre SQL database.
'''
def parse_fhir_bundle_to_df(bundle_data: dict) -> pd.DataFrame:
    extracted_records = []

    if isinstance(bundle_data, list):
        for bundle in bundle_data:
            features = extract_features(bundle)
            if features:
                extracted_records.append(features)
    elif bundle_data.get("resourceType") == "Bundle":
        features = extract_features(bundle_data)
        if features:
            extracted_records.append(features)

    df = pd.DataFrame(extracted_records)

    return df