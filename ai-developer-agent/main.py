import json
from langgraph.graph import StateGraph, START, END
from state import GraphState
from architect import backend_architect_agent, frontend_architect_agent  
from backend_planner import backend_planner_agent
from frontend_planner import frontend_planner_agent
from sync_agent import reviewer_sync_agent

# 1. Workflow start
workflow = StateGraph(GraphState)

# 2. Adding the 4 nodes
workflow.add_node("backend_architect_node", backend_architect_agent)
workflow.add_node("frontend_architect_node", frontend_architect_agent)
workflow.add_node("backend_planner_node", backend_planner_agent)
workflow.add_node("frontend_planner_node", frontend_planner_agent)
workflow.add_node("sync_node", reviewer_sync_agent)

# 3. Microservice pipeline 
workflow.add_edge(START, "backend_architect_node")
workflow.add_edge("backend_architect_node", "frontend_architect_node") 
workflow.add_edge("frontend_architect_node", "backend_planner_node") 
workflow.add_edge("backend_planner_node", "frontend_planner_node")   
workflow.add_edge("frontend_planner_node", "sync_node")
workflow.add_edge("sync_node", END)                     

# 4. Compile 
app = workflow.compile()

sample_srs_json = """
{
  "software_requirements_specification": {
    "document_control": {
      "title": "Software Requirements Specification (SRS) with Data Types for Enterprise Hospital Management System (HMS)",
      "standard_format": "IEEE Std 830-1998 / ISO/IEC/IEEE 29148",
      "version": "1.1.0",
      "status": "Approved for Engineering Implementation",
      "last_updated": "2026-05-31",
      "confidentiality": "Restricted / Institutional Internal Use Only"
    },
    "1_introduction": {
      "1_1_purpose": "This document specifies the comprehensive functional, non-functional, and data architecture requirements for the enterprise Hospital Management System (HMS). It serves as the single source of truth for both structural system behavior and data type constraints across database and API integration boundaries.",
      "1_2_scope": {
        "product_name": "Enterprise Hospital Management System (HMS)",
        "in_scope_core_modules": [
          "Outpatient Department (OPD) & Inpatient Department (IPD) Management",
          "Electronic Health Records (EHR) with longitudinal data tracking",
          "Real-time Appointment Scheduling & Queue Orchestration Engine",
          "Centralized Pharmacy & Inventory Control Management",
          "Medical Billing, Insurance Claims Processing & Revenue Cycle Management",
          "Laboratory Information System (LIS) & Radiology Information System (RIS) with PACS Integration"
        ],
        "out_of_scope": [
          "Direct mechanical maintenance or low-level firmware support of physical biomedical IoT sensor hardware.",
          "Direct processing or clearing of financial credit card transactions (delegated entirely to external PCI-DSS compliant payment gateways via secure tokens)."
        ]
      },
      "1_3_definitions_acronyms_abbreviations": [
        { "term": "EHR / EMR", "definition": "Electronic Health Record / Electronic Medical Record" },
        { "term": "HL7", "definition": "Health Level Seven International (standard framework for transferring clinical and administrative data)" },
        { "term": "FHIR", "definition": "Fast Healthcare Interoperability Resources (REST-based modern healthcare data exchange protocol)" },
        { "term": "PACS", "definition": "Picture Archiving and Communication System (medical imaging technology for storage and convenient access)" },
        { "term": "DICOM", "definition": "Digital Imaging and Communications in Medicine (standard for handling, storing, printing, and transmitting medical imaging info)" },
        { "term": "HIPAA", "definition": "Health Insurance Portability and Accountability Act" },
        { "term": "ICD-11", "definition": "International Classification of Diseases, 11th Revision" },
        { "term": "SNOMED CT", "definition": "Systematized Nomenclature of Medicine -- Clinical Terms" },
        { "term": "RBAC", "definition": "Role-Based Access Control" },
        { "term": "UUID", "definition": "Universally Unique Identifier (128-bit label used for database primary keys)" }
      ],
      "1_4_references": [
        "IEEE Std 830-1998, IEEE Recommended Practice for Software Requirements Specifications.",
        "ISO/IEC/IEEE 29148:2018 Systems and software engineering — Requirements engineering.",
        "Health Insurance Portability and Accountability Act (HIPAA) Security and Privacy Rules (45 CFR Part 160 and Part 164).",
        "HL7 FHIR Release 4 (R4) Framework Core Structural Specifications."
      ],
      "1_5_overview": "This specification is partitioned into four major dimensions: Section 2 outlines system perspectives and user classes; Section 3 details the EARS-compliant functional constraints; Section 4 encapsulates the complete, production-grade Data Dictionary mapping out strict types, sizes, and validation frameworks."
    },
    "2_overall_description": {
      "2_1_product_perspective": "The HMS operates as a centralized web-and-mobile-accessible enterprise system running on a secure cloud or on-premise high-availability containerized microservices architecture. It interfaces natively with legacy insurance clearing houses, external reference laboratories via HL7 messaging engines, and diagnostic imaging hardware through DICOM-compliant PACS servers.",
      "2_2_product_functions": [
        { "id": "F-CORE-01", "function": "Patient Lifecycle Orchestration (Registration, MPI matching, Triage, IPD ADT workflows)", "priority": "Critical" },
        { "id": "F-CORE-02", "function": "Clinical Workflow Automation & CPOE (Order entry, structured EHR notes, drug-interaction parsing)", "priority": "Critical" },
        { "id": "F-CORE-03", "function": "Resource & Asset Management (Operating theater reservations, shift rosters, pharmaceutical reordering)", "priority": "High" },
        { "id": "F-CORE-04", "function": "Financial Cycle Management (Line-item compilation, split insurance invoices, live claim validation)", "priority": "High" }
      ],
      "2_3_user_characteristics": [
        {
          "persona": "System Security Administrator",
          "technical_expertise": "Expert",
          "role_responsibility": "Performs infrastructure configuration, cryptographic key rotation, security audit analysis, and global RBAC privilege provisioning."
        },
        {
          "persona": "Physician / Consultant",
          "technical_expertise": "Intermediate-to-High",
          "role_responsibility": "Requires rapid clinical data entry, immediate longitudinal patient health record access, and sub-second diagnostic image rendering."
        }
      ],
      "2_4_constraints": [
        "All data management models must isolate clinical profiles into decoupled, FHIR-compliant JSON structures to fulfill strict interoperability mandates.",
        "Regulatory standards demand complete alignment with HIPAA rules; Protected Health Information (PHI) must be cryptographically sandboxed at rest and in motion."
      ],
      "2_5_assumptions_and_dependencies": [
        "It is assumed that institutional local area networks (LAN) guarantee a minimum of 1 Gbps continuous throughput.",
        "The system maintains an absolute dependency on the continuous external availability of RxNorm, SNOMED-CT, and ICD-11 dictionary synchronization APIs."
      ]
    },
    "3_specific_requirements": {
      "3_1_external_interface_requirements": {
        "3_1_1_user_interfaces": "All graphical management views shall leverage a responsive fluid grid layout supporting a minimum operational resolution of 1280x720 up to 3840x2160 pixels without text collision.",
        "3_1_2_hardware_interfaces": "The software captures stream sequences from USB/Bluetooth barcode and RFID scanners operating via keyboard emulation profiles.",
        "3_1_3_software_interfaces": "Database architectures combine highly available relational storage clusters (PostgreSQL) with indexed NoSQL document stores for clinical payload structures.",
        "3_1_4_communications_interfaces": "All programmatic network channels enforce TLS v1.3 encryption bindings. APIs must present RESTful and GraphQL endpoints passing payloads structured strictly according to official HL7 FHIR schema configurations."
      },
      "3_2_functional_requirements": [
        {
          "id": "FR-REG-001",
          "module": "Patient Registration & Master Patient Index (MPI)",
          "feature": "Unique Patient Identification & Deduplication",
          "condition_event": "When an operator submits a new patient registration profile",
          "system_response": "The system shall invoke an advanced phonetic matching algorithm (Double Metaphone) against the existing database, flag potential duplicate accounts matching greater than an 85% score threshold, and if clear, assign a globally unique, non-sequential MPI identifier within 300 milliseconds.",
          "verification_method": "Automated Code Integration Tests / Phonetic Vector Analysis"
        },
        {
          "id": "FR-EHR-002",
          "module": "Electronic Health Records (EHR) & Clinical Workflows",
          "feature": "Immutable Cryptographic Audit Trail Tracking",
          "condition_event": "Whenever an authorized clinical user alters or appends data within an existing Electronic Health Record encounter node",
          "system_response": "The system shall preserve the original state row intact and write a cryptographically signed append-only transaction entry tracking the User ID, Timestamp, Location, Old Value, and New Value into the database audit repository.",
          "verification_method": "Database State Integrity Scans & Cryptographic Signature Validation"
        }
      ],
      "3_3_performance_requirements": [
        { "metric_id": "PR-PERF-001", "metric": "Concurrent User Volumetrics", "target": "Maintain nominal operating conditions while processing at least 15,000 active concurrent connections." },
        { "metric_id": "PR-PERF-002", "metric": "API Search Response Latency", "target": "99% of structural relational query profiles must complete and return data elements in less than 150 milliseconds." }
      ],
      "3_4_software_system_attributes": {
        "security": "All data spaces containing Protected Health Information (PHI) must employ full AES-256-GCM block encryption arrays at rest. Multi-factor validation layers are mandatory via OIDC/OAuth2 protocols.",
        "reliability": "Microservices must deploy within multi-zone self-healing orchestration pools (Kubernetes clusters)."
      }
    },
    "4_data_dictionary_and_type_mappings": {
      "4_1_patient_profile_entity": {
        "description": "Represents core demographic details map to the Master Patient Index (MPI) database table.",
        "fields": [
          { "field_name": "mpi_id", "data_type": "UUIDv4", "db_mapping": "UUID UNIQUE PRIMARY KEY", "nullable": false, "validation": "RFC 4122 standard layout format" },
          { "field_name": "legal_first_name", "data_type": "String", "db_mapping": "VARCHAR(100)", "nullable": false, "validation": "Length 1-100 characters, alphanumeric exclusions apply" },
          { "field_name": "legal_last_name", "data_type": "String", "db_mapping": "VARCHAR(100)", "nullable": false, "validation": "Length 1-100 characters, alphanumeric exclusions apply" },
          { "field_name": "date_of_birth", "data_type": "Date", "db_mapping": "DATE", "nullable": false, "validation": "ISO 8601 standard calendar date format (YYYY-MM-DD), must be historical" },
          { "field_name": "gender_identity", "data_type": "Enum", "db_mapping": "VARCHAR(20)", "nullable": false, "validation": "Allowed structural flags: ['MALE', 'FEMALE', 'OTHER', 'UNDISCLOSED']" },
          { "field_name": "primary_contact_phone", "data_type": "String", "db_mapping": "VARCHAR(30)", "nullable": false, "validation": "E.164 compliant telephone format regex: ^\\+[1-9]\\d{1,14}$" },
          { "field_name": "emergency_contact_json", "data_type": "JSONB", "db_mapping": "JSONB", "nullable": true, "validation": "Structured sub-keys: name (string), relationship (string), phone (string)" },
          { "field_name": "is_active", "data_type": "Boolean", "db_mapping": "BOOLEAN DEFAULT TRUE", "nullable": false, "validation": "True or False flags only" }
        ]
      },
      "4_2_appointment_scheduling_entity": {
        "description": "Orchestrates resource availability reservations within the structural clinic schedules calendar subsystem.",
        "fields": [
          { "field_name": "appointment_id", "data_type": "UUIDv4", "db_mapping": "UUID UNIQUE PRIMARY KEY", "nullable": false, "validation": "RFC 4122 system string generation" },
          { "field_name": "patient_mpi_id", "data_type": "UUIDv4", "db_mapping": "UUID REFERENCES patient_profile(mpi_id)", "nullable": false, "validation": "Must exist inside valid patient records pool" },
          { "field_name": "practitioner_id", "data_type": "UUIDv4", "db_mapping": "UUID REFERENCES staff_profile(staff_id)", "nullable": false, "validation": "Must match active authorized provider directory keys" },
          { "field_name": "scheduled_start_time", "data_type": "DateTimeTimezone", "db_mapping": "TIMESTAMPTZ", "nullable": false, "validation": "ISO 8601 format (YYYY-MM-DDThh:mm:ssZ), must be inside future parameters" },
          { "field_name": "scheduled_duration_minutes", "data_type": "Integer", "db_mapping": "SMALLINT", "nullable": false, "validation": "Numeric bounds: 5 to 480 minutes" },
          { "field_name": "status_flag", "data_type": "Enum", "db_mapping": "VARCHAR(25)", "nullable": false, "validation": "Allowed options: ['SCHEDULED', 'ARRIVED', 'IN_CONSULTATION', 'COMPLETED', 'NOSHOW', 'CANCELLED']" }
        ]
      },
      "4_3_ehr_encounter_node": {
        "description": "Houses critical medical charting details captured via the Clinical Order Entry pipelines.",
        "fields": [
          { "field_name": "encounter_id", "data_type": "UUIDv4", "db_mapping": "UUID UNIQUE PRIMARY KEY", "nullable": false, "validation": "RFC 4122 tracking hash configuration" },
          { "field_name": "appointment_context_id", "data_type": "UUIDv4", "db_mapping": "UUID REFERENCES appointment_scheduling(appointment_id)", "nullable": true, "validation": "Nullable index string matching session triggers" },
          { "field_name": "snomed_clinical_diagnoses", "data_type": "Array(String)", "db_mapping": "VARCHAR(50)[]", "nullable": true, "validation": "Array elements must explicitly validate against active SNOMED-CT code lists" },
          { "field_name": "icd11_billing_codes", "data_type": "Array(String)", "db_mapping": "VARCHAR(20)[]", "nullable": true, "validation": "Array maps directly onto official World Health Organization classification vectors" },
          { "field_name": "clinical_narrative_notes", "data_type": "Text", "db_mapping": "TEXT", "nullable": false, "validation": "Sanitized rich-text block storage with no payload code compilation allowance" },
          { "field_name": "fhir_payload_snapshot", "data_type": "JSONB", "db_mapping": "JSONB", "nullable": false, "validation": "Must perfectly pass structural verification tests matching the HL7 FHIR Encounter Schema standard" }
        ]
      },
      "4_4_billing_invoice_ledger": {
        "description": "Tracks systemic line items, financial ledgers, and real-time claim validation summaries.",
        "fields": [
          { "field_name": "invoice_id", "data_type": "UUIDv4", "db_mapping": "UUID UNIQUE PRIMARY KEY", "nullable": false, "validation": "Standard unique internal tracking ledger token" },
          { "field_name": "encounter_context_id", "data_type": "UUIDv4", "db_mapping": "UUID REFERENCES ehr_encounter(encounter_id)", "nullable": false, "validation": "Explicit correlation mapping linking medical sessions to financials" },
          { "field_name": "gross_charge_amount", "data_type": "Decimal/Numeric", "db_mapping": "NUMERIC(12, 2)", "nullable": false, "validation": "Precision mapping formatting: up to 10 scale units, 2 mantissa points (e.g., 9999999999.99), non-negative constraints apply" },
          { "field_name": "insurance_coverage_amount", "data_type": "Decimal/Numeric", "db_mapping": "NUMERIC(12, 2)", "nullable": false, "validation": "Calculated field reflecting structural ANSI X12 271 return balances" },
          { "field_name": "patient_responsibility_balance", "data_type": "Decimal/Numeric", "db_mapping": "NUMERIC(12, 2)", "nullable": false, "validation": "Formula validation evaluation: gross_charge_amount minus insurance_coverage_amount" },
          { "field_name": "currency_code", "data_type": "String", "db_mapping": "CHAR(3) DEFAULT 'USD'", "nullable": false, "validation": "ISO 4217 structural 3-letter capital currency flags" },
          { "field_name": "created_timestamp", "data_type": "DateTimeTimezone", "db_mapping": "TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP", "nullable": false, "validation": "Auto-assigned system capture matrices tracking entry creation timelines" }
        ]
      }
    }
  }
}
"""

if __name__ == "__main__":
    print("=== ENTERPRISE MULTI-AGENT SYSTEM STARTING ===")
    initial_state = {"srs_input": sample_srs_json}
    
    final_output = app.invoke(initial_state)
    print("\n=== SUCCESS: ALL STRATEGIC BLUEPRINTS GENERATED IN /plans FOLDER ===")