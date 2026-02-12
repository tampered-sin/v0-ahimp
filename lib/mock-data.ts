import {
  type InventoryItem,
  type Supplier,
  type Department,
  type PurchaseOrder,
  type User,
  type Alert,
  type ActivityLog,
  Category,
  StockStatus,
  Role,
  OrderStatus,
  AlertType,
  AlertSeverity,
} from "./types"

export const users: User[] = [
  { id: "u1", name: "Dr. Sarah Chen", email: "sarah.chen@hospital.org", role: Role.Admin, departmentId: "d1", avatar: "SC" },
  { id: "u2", name: "James Rodriguez", email: "james.r@hospital.org", role: Role.Pharmacist, departmentId: "d1", avatar: "JR" },
  { id: "u3", name: "Emily Watson", email: "emily.w@hospital.org", role: Role.Nurse, departmentId: "d3", avatar: "EW" },
  { id: "u4", name: "Dr. Michael Park", email: "michael.p@hospital.org", role: Role.DepartmentHead, departmentId: "d4", avatar: "MP" },
]

export const departments: Department[] = [
  { id: "d1", name: "Pharmacy", head: "Dr. Sarah Chen", budget: 500000, spent: 345000 },
  { id: "d2", name: "Surgery", head: "Dr. Alan Wright", budget: 750000, spent: 620000 },
  { id: "d3", name: "Emergency", head: "Dr. Lisa Park", budget: 400000, spent: 310000 },
  { id: "d4", name: "ICU", head: "Dr. Michael Park", budget: 600000, spent: 480000 },
  { id: "d5", name: "Pediatrics", head: "Dr. Nina Patel", budget: 350000, spent: 210000 },
  { id: "d6", name: "Laboratory", head: "Dr. Kevin Zhao", budget: 300000, spent: 195000 },
]

export const suppliers: Supplier[] = [
  { id: "s1", name: "MedPharm Distributors", contact: "Robert Allen", email: "orders@medpharm.com", phone: "+1-555-0101", address: "123 Medical Ave, Boston, MA", rating: 4.8, itemsSupplied: 156 },
  { id: "s2", name: "SurgiTech Solutions", contact: "Diana Lee", email: "sales@surgitech.com", phone: "+1-555-0102", address: "456 Tech Park, San Jose, CA", rating: 4.5, itemsSupplied: 89 },
  { id: "s3", name: "BioLab Supplies Inc", contact: "Marcus Brown", email: "info@biolab.com", phone: "+1-555-0103", address: "789 Science Blvd, Chicago, IL", rating: 4.2, itemsSupplied: 67 },
  { id: "s4", name: "SafeGuard PPE Co", contact: "Anna Martinez", email: "supply@safeguard.com", phone: "+1-555-0104", address: "321 Safety Ln, Houston, TX", rating: 4.6, itemsSupplied: 45 },
  { id: "s5", name: "BloodCare Systems", contact: "Thomas Grant", email: "orders@bloodcare.com", phone: "+1-555-0105", address: "654 Health Dr, Philadelphia, PA", rating: 4.9, itemsSupplied: 34 },
  { id: "s6", name: "PharmaGlobal Ltd", contact: "Sophia Kim", email: "sales@pharmaglobal.com", phone: "+1-555-0106", address: "987 Pharma Way, New York, NY", rating: 4.3, itemsSupplied: 112 },
  { id: "s7", name: "OrthoMed Devices", contact: "David Wilson", email: "info@orthomed.com", phone: "+1-555-0107", address: "147 Device Rd, Atlanta, GA", rating: 4.7, itemsSupplied: 78 },
  { id: "s8", name: "CleanRoom Essentials", contact: "Rachel Green", email: "orders@cleanroom.com", phone: "+1-555-0108", address: "258 Clean St, Denver, CO", rating: 4.1, itemsSupplied: 53 },
]

export const inventoryItems: InventoryItem[] = [
  // Medicines
  { id: "i1", name: "Amoxicillin 500mg", category: Category.Medicines, sku: "MED-AMX-500", quantity: 2500, unit: "Capsules", reorderLevel: 500, unitPrice: 0.45, supplierId: "s1", departmentId: "d1", batchNumber: "B2024-001", expiryDate: "2026-08-15", location: "Pharmacy Store A1", status: StockStatus.InStock, lastRestocked: "2025-12-01", notes: "Broad-spectrum antibiotic" },
  { id: "i2", name: "Ibuprofen 200mg", category: Category.Medicines, sku: "MED-IBU-200", quantity: 1800, unit: "Tablets", reorderLevel: 400, unitPrice: 0.12, supplierId: "s1", departmentId: "d1", batchNumber: "B2024-002", expiryDate: "2026-11-20", location: "Pharmacy Store A2", status: StockStatus.InStock, lastRestocked: "2025-11-15", notes: "Anti-inflammatory pain relief" },
  { id: "i3", name: "Morphine Sulfate 10mg", category: Category.Medicines, sku: "MED-MOR-010", quantity: 120, unit: "Vials", reorderLevel: 150, unitPrice: 8.50, supplierId: "s6", departmentId: "d4", batchNumber: "B2024-003", expiryDate: "2026-03-10", location: "Controlled Substance Cabinet", status: StockStatus.LowStock, lastRestocked: "2025-10-20", notes: "Controlled substance - requires DEA documentation" },
  { id: "i4", name: "Epinephrine 1mg/mL", category: Category.Medicines, sku: "MED-EPI-001", quantity: 350, unit: "Auto-injectors", reorderLevel: 100, unitPrice: 35.00, supplierId: "s1", departmentId: "d3", batchNumber: "B2024-004", expiryDate: "2026-06-30", location: "Emergency Cart E1", status: StockStatus.InStock, lastRestocked: "2025-11-01", notes: "Emergency anaphylaxis treatment" },
  { id: "i5", name: "Insulin Glargine 100U/mL", category: Category.Medicines, sku: "MED-INS-100", quantity: 85, unit: "Pens", reorderLevel: 100, unitPrice: 42.00, supplierId: "s6", departmentId: "d1", batchNumber: "B2024-005", expiryDate: "2026-04-15", location: "Refrigerated Storage R1", status: StockStatus.LowStock, lastRestocked: "2025-09-15", notes: "Long-acting insulin - refrigerate" },
  { id: "i6", name: "Ceftriaxone 1g", category: Category.Medicines, sku: "MED-CEF-001", quantity: 600, unit: "Vials", reorderLevel: 200, unitPrice: 3.20, supplierId: "s1", departmentId: "d1", batchNumber: "B2024-006", expiryDate: "2027-01-20", location: "Pharmacy Store A3", status: StockStatus.InStock, lastRestocked: "2025-12-10", notes: "Third-generation cephalosporin" },
  { id: "i7", name: "Paracetamol 500mg", category: Category.Medicines, sku: "MED-PAR-500", quantity: 5000, unit: "Tablets", reorderLevel: 1000, unitPrice: 0.08, supplierId: "s1", departmentId: "d1", batchNumber: "B2024-007", expiryDate: "2027-03-15", location: "Pharmacy Store A1", status: StockStatus.InStock, lastRestocked: "2026-01-05", notes: "General pain and fever relief" },
  { id: "i8", name: "Omeprazole 20mg", category: Category.Medicines, sku: "MED-OME-020", quantity: 30, unit: "Capsules", reorderLevel: 300, unitPrice: 0.35, supplierId: "s6", departmentId: "d1", batchNumber: "B2023-089", expiryDate: "2026-02-28", location: "Pharmacy Store A2", status: StockStatus.LowStock, lastRestocked: "2025-06-20", notes: "Proton pump inhibitor - CRITICAL LOW" },

  // Equipment
  { id: "i9", name: "Patient Monitor (Vital Signs)", category: Category.Equipment, sku: "EQP-MON-001", quantity: 24, unit: "Units", reorderLevel: 5, unitPrice: 4500.00, supplierId: "s2", departmentId: "d4", batchNumber: "EQ-2024-001", expiryDate: "N/A", location: "ICU Equipment Room", status: StockStatus.InStock, lastRestocked: "2025-08-01", notes: "Multi-parameter vital signs monitor" },
  { id: "i10", name: "Infusion Pump", category: Category.Equipment, sku: "EQP-INF-001", quantity: 45, unit: "Units", reorderLevel: 10, unitPrice: 2800.00, supplierId: "s2", departmentId: "d4", batchNumber: "EQ-2024-002", expiryDate: "N/A", location: "ICU Equipment Room", status: StockStatus.InStock, lastRestocked: "2025-09-15", notes: "Programmable volumetric infusion pump" },
  { id: "i11", name: "Defibrillator AED", category: Category.Equipment, sku: "EQP-DEF-001", quantity: 8, unit: "Units", reorderLevel: 3, unitPrice: 1200.00, supplierId: "s2", departmentId: "d3", batchNumber: "EQ-2024-003", expiryDate: "N/A", location: "Emergency Department", status: StockStatus.InStock, lastRestocked: "2025-07-10", notes: "Automated external defibrillator" },
  { id: "i12", name: "Ventilator (ICU Grade)", category: Category.Equipment, sku: "EQP-VEN-001", quantity: 3, unit: "Units", reorderLevel: 5, unitPrice: 25000.00, supplierId: "s2", departmentId: "d4", batchNumber: "EQ-2024-004", expiryDate: "N/A", location: "ICU", status: StockStatus.LowStock, lastRestocked: "2025-06-01", notes: "Critical care ventilator - LOW STOCK" },
  { id: "i13", name: "Pulse Oximeter (Portable)", category: Category.Equipment, sku: "EQP-POX-001", quantity: 60, unit: "Units", reorderLevel: 15, unitPrice: 85.00, supplierId: "s7", departmentId: "d3", batchNumber: "EQ-2024-005", expiryDate: "N/A", location: "General Storage G2", status: StockStatus.InStock, lastRestocked: "2025-11-20", notes: "Fingertip pulse oximeter" },
  { id: "i14", name: "Wheelchair (Standard)", category: Category.Equipment, sku: "EQP-WCH-001", quantity: 18, unit: "Units", reorderLevel: 5, unitPrice: 350.00, supplierId: "s7", departmentId: "d3", batchNumber: "EQ-2024-006", expiryDate: "N/A", location: "Ground Floor Storage", status: StockStatus.InStock, lastRestocked: "2025-10-01", notes: "Standard manual wheelchair" },

  // Surgical Supplies
  { id: "i15", name: "Surgical Gloves (Sterile)", category: Category.Surgical, sku: "SRG-GLV-001", quantity: 8000, unit: "Pairs", reorderLevel: 2000, unitPrice: 0.65, supplierId: "s4", departmentId: "d2", batchNumber: "SG-2024-001", expiryDate: "2027-05-20", location: "Surgery Store S1", status: StockStatus.InStock, lastRestocked: "2026-01-10", notes: "Latex-free sterile surgical gloves" },
  { id: "i16", name: "Suture Kit (Absorbable)", category: Category.Surgical, sku: "SRG-STR-001", quantity: 250, unit: "Kits", reorderLevel: 50, unitPrice: 12.50, supplierId: "s2", departmentId: "d2", batchNumber: "SG-2024-002", expiryDate: "2027-08-30", location: "Surgery Store S2", status: StockStatus.InStock, lastRestocked: "2025-12-15", notes: "Polyglycolic acid absorbable sutures" },
  { id: "i17", name: "Scalpel Blades #10", category: Category.Surgical, sku: "SRG-SCL-010", quantity: 400, unit: "Blades", reorderLevel: 100, unitPrice: 0.85, supplierId: "s2", departmentId: "d2", batchNumber: "SG-2024-003", expiryDate: "2028-01-15", location: "Surgery Store S1", status: StockStatus.InStock, lastRestocked: "2025-11-25", notes: "Carbon steel scalpel blades" },
  { id: "i18", name: "Surgical Drapes (Sterile)", category: Category.Surgical, sku: "SRG-DRP-001", quantity: 45, unit: "Packs", reorderLevel: 60, unitPrice: 8.75, supplierId: "s8", departmentId: "d2", batchNumber: "SG-2024-004", expiryDate: "2027-04-10", location: "Surgery Store S3", status: StockStatus.LowStock, lastRestocked: "2025-10-05", notes: "Disposable sterile surgical drapes" },
  { id: "i19", name: "Hemostatic Forceps", category: Category.Surgical, sku: "SRG-HMF-001", quantity: 30, unit: "Units", reorderLevel: 10, unitPrice: 45.00, supplierId: "s2", departmentId: "d2", batchNumber: "SG-2024-005", expiryDate: "N/A", location: "Surgery Store S2", status: StockStatus.InStock, lastRestocked: "2025-09-20", notes: "Stainless steel hemostatic forceps" },

  // PPE
  { id: "i20", name: "N95 Respirator Masks", category: Category.PPE, sku: "PPE-N95-001", quantity: 3500, unit: "Masks", reorderLevel: 1000, unitPrice: 1.85, supplierId: "s4", departmentId: "d3", batchNumber: "PP-2024-001", expiryDate: "2027-12-31", location: "PPE Storage P1", status: StockStatus.InStock, lastRestocked: "2026-01-15", notes: "NIOSH-approved N95 respirators" },
  { id: "i21", name: "Disposable Gowns (Isolation)", category: Category.PPE, sku: "PPE-GWN-001", quantity: 1200, unit: "Gowns", reorderLevel: 300, unitPrice: 2.40, supplierId: "s4", departmentId: "d3", batchNumber: "PP-2024-002", expiryDate: "2027-10-15", location: "PPE Storage P1", status: StockStatus.InStock, lastRestocked: "2025-12-20", notes: "Level 2 fluid-resistant isolation gowns" },
  { id: "i22", name: "Face Shields", category: Category.PPE, sku: "PPE-FSH-001", quantity: 180, unit: "Shields", reorderLevel: 200, unitPrice: 3.50, supplierId: "s4", departmentId: "d3", batchNumber: "PP-2024-003", expiryDate: "2028-06-30", location: "PPE Storage P2", status: StockStatus.LowStock, lastRestocked: "2025-08-10", notes: "Full-face protective shields" },
  { id: "i23", name: "Nitrile Exam Gloves (M)", category: Category.PPE, sku: "PPE-GLV-M01", quantity: 15000, unit: "Gloves", reorderLevel: 5000, unitPrice: 0.12, supplierId: "s4", departmentId: "d3", batchNumber: "PP-2024-004", expiryDate: "2028-03-20", location: "PPE Storage P1", status: StockStatus.InStock, lastRestocked: "2026-01-20", notes: "Powder-free nitrile examination gloves" },

  // Lab Reagents
  { id: "i24", name: "Blood Glucose Test Strips", category: Category.LabReagents, sku: "LAB-GLS-001", quantity: 2000, unit: "Strips", reorderLevel: 500, unitPrice: 0.55, supplierId: "s3", departmentId: "d6", batchNumber: "LB-2024-001", expiryDate: "2026-09-30", location: "Lab Storage L1", status: StockStatus.InStock, lastRestocked: "2025-11-10", notes: "Compatible with AccuCheck meters" },
  { id: "i25", name: "Urinalysis Dipstick (10-param)", category: Category.LabReagents, sku: "LAB-URI-010", quantity: 800, unit: "Strips", reorderLevel: 200, unitPrice: 0.75, supplierId: "s3", departmentId: "d6", batchNumber: "LB-2024-002", expiryDate: "2026-07-15", location: "Lab Storage L1", status: StockStatus.InStock, lastRestocked: "2025-10-25", notes: "10-parameter urinalysis test strips" },
  { id: "i26", name: "PCR Reagent Kit", category: Category.LabReagents, sku: "LAB-PCR-001", quantity: 15, unit: "Kits", reorderLevel: 20, unitPrice: 285.00, supplierId: "s3", departmentId: "d6", batchNumber: "LB-2024-003", expiryDate: "2026-04-20", location: "Lab Refrigerator LR1", status: StockStatus.LowStock, lastRestocked: "2025-09-01", notes: "Real-time PCR detection kit - refrigerate" },
  { id: "i27", name: "Hematology Reagent Pack", category: Category.LabReagents, sku: "LAB-HEM-001", quantity: 40, unit: "Packs", reorderLevel: 10, unitPrice: 120.00, supplierId: "s3", departmentId: "d6", batchNumber: "LB-2024-004", expiryDate: "2026-12-31", location: "Lab Storage L2", status: StockStatus.InStock, lastRestocked: "2025-12-05", notes: "Complete hematology analyzer reagent pack" },

  // Blood Bank
  { id: "i28", name: "Packed Red Blood Cells (O+)", category: Category.BloodBank, sku: "BLD-RBC-OP", quantity: 45, unit: "Units", reorderLevel: 30, unitPrice: 225.00, supplierId: "s5", departmentId: "d2", batchNumber: "BB-2024-001", expiryDate: "2026-03-15", location: "Blood Bank Refrigerator", status: StockStatus.InStock, lastRestocked: "2026-02-01", notes: "Type O+ packed red blood cells" },
  { id: "i29", name: "Fresh Frozen Plasma (AB)", category: Category.BloodBank, sku: "BLD-FFP-AB", quantity: 12, unit: "Units", reorderLevel: 15, unitPrice: 180.00, supplierId: "s5", departmentId: "d2", batchNumber: "BB-2024-002", expiryDate: "2026-08-20", location: "Blood Bank Freezer", status: StockStatus.LowStock, lastRestocked: "2026-01-15", notes: "Type AB fresh frozen plasma" },
  { id: "i30", name: "Platelet Concentrate", category: Category.BloodBank, sku: "BLD-PLT-001", quantity: 8, unit: "Units", reorderLevel: 10, unitPrice: 550.00, supplierId: "s5", departmentId: "d2", batchNumber: "BB-2024-003", expiryDate: "2026-02-20", location: "Blood Bank Agitator", status: StockStatus.LowStock, lastRestocked: "2026-02-10", notes: "Pooled platelet concentrate - 5 day shelf life" },
  { id: "i31", name: "Cryoprecipitate", category: Category.BloodBank, sku: "BLD-CRY-001", quantity: 25, unit: "Units", reorderLevel: 10, unitPrice: 95.00, supplierId: "s5", departmentId: "d2", batchNumber: "BB-2024-004", expiryDate: "2027-01-30", location: "Blood Bank Freezer", status: StockStatus.InStock, lastRestocked: "2025-12-20", notes: "Cryoprecipitated antihemophilic factor" },

  // More medicines
  { id: "i32", name: "Aspirin 81mg", category: Category.Medicines, sku: "MED-ASP-081", quantity: 3000, unit: "Tablets", reorderLevel: 500, unitPrice: 0.05, supplierId: "s1", departmentId: "d1", batchNumber: "B2024-032", expiryDate: "2027-06-15", location: "Pharmacy Store A1", status: StockStatus.InStock, lastRestocked: "2025-12-15", notes: "Low-dose aspirin for cardiac patients" },
  { id: "i33", name: "Metformin 500mg", category: Category.Medicines, sku: "MED-MET-500", quantity: 1500, unit: "Tablets", reorderLevel: 300, unitPrice: 0.15, supplierId: "s6", departmentId: "d1", batchNumber: "B2024-033", expiryDate: "2027-09-30", location: "Pharmacy Store A2", status: StockStatus.InStock, lastRestocked: "2026-01-10", notes: "Type 2 diabetes management" },
  { id: "i34", name: "Lisinopril 10mg", category: Category.Medicines, sku: "MED-LIS-010", quantity: 900, unit: "Tablets", reorderLevel: 200, unitPrice: 0.22, supplierId: "s1", departmentId: "d1", batchNumber: "B2024-034", expiryDate: "2027-04-20", location: "Pharmacy Store A3", status: StockStatus.InStock, lastRestocked: "2025-11-30", notes: "ACE inhibitor for hypertension" },
  { id: "i35", name: "Warfarin 5mg", category: Category.Medicines, sku: "MED-WAR-005", quantity: 0, unit: "Tablets", reorderLevel: 200, unitPrice: 0.18, supplierId: "s6", departmentId: "d1", batchNumber: "B2024-035", expiryDate: "2027-02-28", location: "Pharmacy Store A1", status: StockStatus.OutOfStock, lastRestocked: "2025-08-15", notes: "Anticoagulant - REORDER IMMEDIATELY" },

  // More equipment
  { id: "i36", name: "ECG Machine (12-lead)", category: Category.Equipment, sku: "EQP-ECG-012", quantity: 6, unit: "Units", reorderLevel: 2, unitPrice: 3500.00, supplierId: "s2", departmentId: "d4", batchNumber: "EQ-2024-036", expiryDate: "N/A", location: "Cardiology Department", status: StockStatus.InStock, lastRestocked: "2025-07-20", notes: "12-lead electrocardiogram machine" },
  { id: "i37", name: "Syringe Pump", category: Category.Equipment, sku: "EQP-SYP-001", quantity: 20, unit: "Units", reorderLevel: 5, unitPrice: 1800.00, supplierId: "s2", departmentId: "d4", batchNumber: "EQ-2024-037", expiryDate: "N/A", location: "ICU Equipment Room", status: StockStatus.InStock, lastRestocked: "2025-10-15", notes: "Precision syringe pump for ICU" },

  // More PPE
  { id: "i38", name: "Surgical Caps", category: Category.PPE, sku: "PPE-CAP-001", quantity: 2500, unit: "Caps", reorderLevel: 500, unitPrice: 0.35, supplierId: "s8", departmentId: "d2", batchNumber: "PP-2024-038", expiryDate: "2028-12-31", location: "Surgery Store S1", status: StockStatus.InStock, lastRestocked: "2026-01-05", notes: "Disposable bouffant surgical caps" },
  { id: "i39", name: "Shoe Covers (Disposable)", category: Category.PPE, sku: "PPE-SHO-001", quantity: 4000, unit: "Pairs", reorderLevel: 1000, unitPrice: 0.25, supplierId: "s8", departmentId: "d2", batchNumber: "PP-2024-039", expiryDate: "2028-12-31", location: "General Storage G1", status: StockStatus.InStock, lastRestocked: "2025-12-28", notes: "Non-skid disposable shoe covers" },

  // More surgical
  { id: "i40", name: "Catheter (Foley 16Fr)", category: Category.Surgical, sku: "SRG-CTH-016", quantity: 150, unit: "Units", reorderLevel: 50, unitPrice: 4.50, supplierId: "s2", departmentId: "d2", batchNumber: "SG-2024-040", expiryDate: "2027-11-15", location: "Surgery Store S3", status: StockStatus.InStock, lastRestocked: "2025-11-10", notes: "Silicone Foley catheter 16 French" },

  // Expired item example
  { id: "i41", name: "Tetracycline 250mg", category: Category.Medicines, sku: "MED-TET-250", quantity: 200, unit: "Capsules", reorderLevel: 100, unitPrice: 0.30, supplierId: "s1", departmentId: "d1", batchNumber: "B2023-041", expiryDate: "2026-01-15", location: "Pharmacy Store A4", status: StockStatus.Expired, lastRestocked: "2024-12-01", notes: "EXPIRED - Pending disposal" },

  // More lab
  { id: "i42", name: "Rapid Strep Test Kit", category: Category.LabReagents, sku: "LAB-RST-001", quantity: 300, unit: "Tests", reorderLevel: 100, unitPrice: 3.25, supplierId: "s3", departmentId: "d6", batchNumber: "LB-2024-042", expiryDate: "2026-10-20", location: "Lab Storage L1", status: StockStatus.InStock, lastRestocked: "2025-12-01", notes: "Rapid streptococcus A antigen test" },
  { id: "i43", name: "COVID-19 Antigen Test", category: Category.LabReagents, sku: "LAB-COV-001", quantity: 500, unit: "Tests", reorderLevel: 200, unitPrice: 5.50, supplierId: "s3", departmentId: "d6", batchNumber: "LB-2024-043", expiryDate: "2026-06-30", location: "Lab Storage L2", status: StockStatus.InStock, lastRestocked: "2025-11-15", notes: "Rapid antigen detection test for SARS-CoV-2" },

  // More blood bank
  { id: "i44", name: "Packed Red Blood Cells (A-)", category: Category.BloodBank, sku: "BLD-RBC-AN", quantity: 6, unit: "Units", reorderLevel: 10, unitPrice: 225.00, supplierId: "s5", departmentId: "d2", batchNumber: "BB-2024-044", expiryDate: "2026-03-20", location: "Blood Bank Refrigerator", status: StockStatus.LowStock, lastRestocked: "2026-01-28", notes: "Type A- packed RBC - rare type, low inventory" },
  { id: "i45", name: "Whole Blood (O-)", category: Category.BloodBank, sku: "BLD-WHL-ON", quantity: 4, unit: "Units", reorderLevel: 8, unitPrice: 300.00, supplierId: "s5", departmentId: "d2", batchNumber: "BB-2024-045", expiryDate: "2026-03-05", location: "Blood Bank Refrigerator", status: StockStatus.LowStock, lastRestocked: "2026-02-05", notes: "Universal donor whole blood - CRITICAL" },
]

export const purchaseOrders: PurchaseOrder[] = [
  { id: "po1", supplierId: "s1", items: [{ itemId: "i1", itemName: "Amoxicillin 500mg", quantity: 5000, unitPrice: 0.42 }, { itemId: "i2", itemName: "Ibuprofen 200mg", quantity: 3000, unitPrice: 0.11 }], status: OrderStatus.Delivered, orderDate: "2025-12-01", expectedDelivery: "2025-12-08", totalAmount: 2430 },
  { id: "po2", supplierId: "s6", items: [{ itemId: "i3", itemName: "Morphine Sulfate 10mg", quantity: 200, unitPrice: 8.20 }, { itemId: "i5", itemName: "Insulin Glargine 100U/mL", quantity: 150, unitPrice: 40.00 }], status: OrderStatus.Shipped, orderDate: "2026-02-01", expectedDelivery: "2026-02-15", totalAmount: 7640 },
  { id: "po3", supplierId: "s2", items: [{ itemId: "i12", itemName: "Ventilator (ICU Grade)", quantity: 4, unitPrice: 24000.00 }], status: OrderStatus.Approved, orderDate: "2026-02-05", expectedDelivery: "2026-03-01", totalAmount: 96000 },
  { id: "po4", supplierId: "s4", items: [{ itemId: "i22", itemName: "Face Shields", quantity: 500, unitPrice: 3.30 }], status: OrderStatus.Pending, orderDate: "2026-02-10", expectedDelivery: "2026-02-20", totalAmount: 1650 },
  { id: "po5", supplierId: "s5", items: [{ itemId: "i29", itemName: "Fresh Frozen Plasma (AB)", quantity: 20, unitPrice: 175.00 }, { itemId: "i45", itemName: "Whole Blood (O-)", quantity: 15, unitPrice: 290.00 }], status: OrderStatus.Pending, orderDate: "2026-02-11", expectedDelivery: "2026-02-18", totalAmount: 7850 },
  { id: "po6", supplierId: "s3", items: [{ itemId: "i26", itemName: "PCR Reagent Kit", quantity: 30, unitPrice: 278.00 }], status: OrderStatus.Shipped, orderDate: "2026-02-03", expectedDelivery: "2026-02-14", totalAmount: 8340 },
  { id: "po7", supplierId: "s6", items: [{ itemId: "i35", itemName: "Warfarin 5mg", quantity: 1000, unitPrice: 0.17 }, { itemId: "i8", itemName: "Omeprazole 20mg", quantity: 2000, unitPrice: 0.33 }], status: OrderStatus.Approved, orderDate: "2026-02-08", expectedDelivery: "2026-02-22", totalAmount: 830 },
  { id: "po8", supplierId: "s2", items: [{ itemId: "i18", itemName: "Surgical Drapes (Sterile)", quantity: 200, unitPrice: 8.50 }], status: OrderStatus.Pending, orderDate: "2026-02-12", expectedDelivery: "2026-02-25", totalAmount: 1700 },
  { id: "po9", supplierId: "s8", items: [{ itemId: "i38", itemName: "Surgical Caps", quantity: 5000, unitPrice: 0.32 }], status: OrderStatus.Delivered, orderDate: "2025-12-20", expectedDelivery: "2025-12-30", totalAmount: 1600 },
  { id: "po10", supplierId: "s7", items: [{ itemId: "i13", itemName: "Pulse Oximeter (Portable)", quantity: 30, unitPrice: 82.00 }], status: OrderStatus.Delivered, orderDate: "2025-11-10", expectedDelivery: "2025-11-20", totalAmount: 2460 },
]

export const alerts: Alert[] = [
  { id: "a1", type: AlertType.LowStock, severity: AlertSeverity.Critical, message: "Warfarin 5mg is OUT OF STOCK. Immediate reorder required.", itemId: "i35", timestamp: "2026-02-12T08:00:00Z", acknowledged: false },
  { id: "a2", type: AlertType.LowStock, severity: AlertSeverity.Critical, message: "Omeprazole 20mg is critically low (30 units). Reorder level: 300.", itemId: "i8", timestamp: "2026-02-12T08:05:00Z", acknowledged: false },
  { id: "a3", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "Ventilator (ICU Grade) stock is low (3 units). Reorder level: 5.", itemId: "i12", timestamp: "2026-02-11T14:30:00Z", acknowledged: false },
  { id: "a4", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "Morphine Sulfate 10mg below reorder level (120/150 units).", itemId: "i3", timestamp: "2026-02-11T09:15:00Z", acknowledged: true },
  { id: "a5", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "Insulin Glargine 100U/mL below reorder level (85/100 pens).", itemId: "i5", timestamp: "2026-02-10T16:00:00Z", acknowledged: true },
  { id: "a6", type: AlertType.ExpiringSoon, severity: AlertSeverity.Warning, message: "Platelet Concentrate expires in 8 days (Feb 20, 2026).", itemId: "i30", timestamp: "2026-02-12T06:00:00Z", acknowledged: false },
  { id: "a7", type: AlertType.ExpiringSoon, severity: AlertSeverity.Warning, message: "Omeprazole 20mg expires in 16 days (Feb 28, 2026).", itemId: "i8", timestamp: "2026-02-12T06:00:00Z", acknowledged: false },
  { id: "a8", type: AlertType.ExpiringSoon, severity: AlertSeverity.Warning, message: "Morphine Sulfate 10mg expires in 26 days (Mar 10, 2026).", itemId: "i3", timestamp: "2026-02-12T06:00:00Z", acknowledged: false },
  { id: "a9", type: AlertType.Expired, severity: AlertSeverity.Critical, message: "Tetracycline 250mg has EXPIRED (Jan 15, 2026). Dispose immediately.", itemId: "i41", timestamp: "2026-01-15T00:00:00Z", acknowledged: false },
  { id: "a10", type: AlertType.OrderUpdate, severity: AlertSeverity.Info, message: "PO-002 (Morphine + Insulin from PharmaGlobal) has been shipped.", timestamp: "2026-02-08T10:30:00Z", acknowledged: true },
  { id: "a11", type: AlertType.OrderUpdate, severity: AlertSeverity.Info, message: "PO-006 (PCR Reagent Kit from BioLab) has been shipped.", timestamp: "2026-02-07T14:00:00Z", acknowledged: true },
  { id: "a12", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "Face Shields stock low (180 units). Reorder level: 200.", itemId: "i22", timestamp: "2026-02-09T11:00:00Z", acknowledged: false },
  { id: "a13", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "Surgical Drapes (Sterile) below reorder level (45/60 packs).", itemId: "i18", timestamp: "2026-02-10T08:30:00Z", acknowledged: false },
  { id: "a14", type: AlertType.LowStock, severity: AlertSeverity.Critical, message: "Whole Blood (O-) critically low (4 units). Universal donor supply.", itemId: "i45", timestamp: "2026-02-12T07:00:00Z", acknowledged: false },
  { id: "a15", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "Fresh Frozen Plasma (AB) below reorder level (12/15 units).", itemId: "i29", timestamp: "2026-02-11T12:00:00Z", acknowledged: false },
  { id: "a16", type: AlertType.ExpiringSoon, severity: AlertSeverity.Warning, message: "Whole Blood (O-) expires in 21 days (Mar 5, 2026).", itemId: "i45", timestamp: "2026-02-12T06:00:00Z", acknowledged: false },
  { id: "a17", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "PCR Reagent Kit below reorder level (15/20 kits).", itemId: "i26", timestamp: "2026-02-10T10:00:00Z", acknowledged: false },
  { id: "a18", type: AlertType.LowStock, severity: AlertSeverity.Warning, message: "Packed Red Blood Cells (A-) low (6/10 units). Rare blood type.", itemId: "i44", timestamp: "2026-02-12T07:30:00Z", acknowledged: false },
]

export const activityLogs: ActivityLog[] = [
  { id: "log1", action: "Item Restocked", userId: "u2", itemId: "i7", timestamp: "2026-02-12T09:30:00Z", details: "Paracetamol 500mg restocked: +2000 tablets" },
  { id: "log2", action: "Purchase Order Created", userId: "u1", timestamp: "2026-02-12T08:45:00Z", details: "PO-008 created for Surgical Drapes from SurgiTech" },
  { id: "log3", action: "Alert Acknowledged", userId: "u1", timestamp: "2026-02-11T16:20:00Z", details: "Acknowledged low stock alert for Morphine Sulfate" },
  { id: "log4", action: "Item Transferred", userId: "u4", itemId: "i13", timestamp: "2026-02-11T14:00:00Z", details: "5 Pulse Oximeters transferred from Emergency to ICU" },
  { id: "log5", action: "Purchase Order Approved", userId: "u1", timestamp: "2026-02-11T10:30:00Z", details: "PO-003 approved: 4 Ventilators from SurgiTech ($96,000)" },
  { id: "log6", action: "New Item Added", userId: "u1", timestamp: "2026-02-10T11:00:00Z", details: "Added COVID-19 Antigen Test to Lab Reagents inventory" },
  { id: "log7", action: "Supplier Updated", userId: "u1", timestamp: "2026-02-10T09:15:00Z", details: "Updated contact info for BloodCare Systems" },
  { id: "log8", action: "Item Expired", userId: "u2", itemId: "i41", timestamp: "2026-01-15T08:00:00Z", details: "Tetracycline 250mg marked as expired - flagged for disposal" },
  { id: "log9", action: "Department Allocation", userId: "u4", timestamp: "2026-02-09T13:45:00Z", details: "ICU budget allocation updated: $480,000 of $600,000 utilized" },
  { id: "log10", action: "Purchase Order Delivered", userId: "u2", timestamp: "2026-02-08T15:00:00Z", details: "PO-001 delivered: Amoxicillin & Ibuprofen from MedPharm" },
  { id: "log11", action: "Stock Count", userId: "u3", timestamp: "2026-02-07T10:00:00Z", details: "Weekly stock count completed for Emergency Department" },
  { id: "log12", action: "Item Restocked", userId: "u2", itemId: "i20", timestamp: "2026-01-15T14:30:00Z", details: "N95 Respirator Masks restocked: +2000 masks" },
]
