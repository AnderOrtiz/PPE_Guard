import time
from app.services.detection_orchestrator import DetectionOrchestrator

orchestrator = DetectionOrchestrator(area="civil")
orchestrator.start()

time.sleep(10)  # déjalo correr 10 segundos, muévete frente a la cámara

orchestrator.stop()

# python -m scripts.test_orchestrator