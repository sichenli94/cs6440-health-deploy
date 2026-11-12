## Data Generation via Synthea

Our project utilizes [Synthea](https://github.com/synthetichealth/synthea), an open-source patient population simulator, to generate synthetic Electronic Health Records (EHR) in FHIR R4 format. 

### Prerequisites
* **Java**: You must have JDK 11 or higher installed on your system.

### Installation & Execution
To replicate our data generation process, open your terminal and run the following commands:

```bash
# 1. Clone the Synthea repository
git clone [https://github.com/synthetichealth/synthea.git](https://github.com/synthetichealth/synthea.git)
cd synthea

# 2. Build the project
./gradlew build check test    # For Mac/Linux
# gradlew.bat build check test  # For Windows

# 3. Generate the patient population
# Note: To yield a sufficient number of diabetic patients with at least one 
# inpatient admission for our cohort, we generate a baseline population of 5,000.
./run_synthea -p 5000
