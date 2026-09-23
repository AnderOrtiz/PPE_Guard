from app.services.camera_service import capture_single_frame
from app.services.face_service import get_face_embedding

frame = capture_single_frame()
embedding = get_face_embedding(frame)

if embedding is None:
    print("No se detectó ningún rostro (o se detectó más de uno).")
else:
    print(f"Embedding calculado, dimensión: {len(embedding)}")
    print(embedding[:5], "...")
    
    
# python -m scripts.test_face_service