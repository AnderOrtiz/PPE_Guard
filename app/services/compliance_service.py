class ComplianceService:
    def __init__(self):
        self.DIRECT_VIOLATIONS = {
            "NO-Hardhat": "Falta casco de seguridad",
            "NO-Mask": "Falta mascarilla",
            "NO-Safety Vest": "Falta chaleco reflectivo"
        }
        self.REQUIRED_PPE = {"Hardhat", "Mask", "Safety Vest"}

    def evaluate_compliance(self, detections: list[dict]) -> dict:
        detected_classes = [d["class_name"] for d in detections]

        alerts = []
        is_compliant = True

        for class_name in detected_classes:
            if class_name in self.DIRECT_VIOLATIONS:
                is_compliant = False
                alerts.append(self.DIRECT_VIOLATIONS[class_name])

        unique_alerts = list(set(alerts))
        person_count = detected_classes.count("Person")

        return {
            "is_compliant": is_compliant,
            "person_count": person_count,
            "alerts": unique_alerts,
            "raw_detections": detections
        }


compliance_service = ComplianceService()