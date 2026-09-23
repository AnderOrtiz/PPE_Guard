# PPE Guard - Project Instructions

## Facial Recognition & Enrollment System

These instructions define the architectural and technical requirements for the live facial recognition and enrollment subsystem.

### Architectural Core Principles
- **No Photo Uploads:** The system does NOT upload or store raw images of faces. Instead, it captures the face live from the camera feed and immediately calculates its mathematical representation (embedding).
- **Core Concept (Embeddings):** A face embedding is a high-dimensional vector of numbers representing the unique features of a face. Comparing two faces is reduced to measuring the distance between their vectors (e.g., cosine distance), rather than direct image comparison.

### Implementation Details
- **Library Selection:** Install and use `deepface` (this avoids the compilation complexity of `dlib` required by alternative libraries like `face_recognition`).
- **Enrollment Flow / Endpoint:**
  1. Open the camera stream.
  2. Capture a single frame.
  3. Validate that exactly one face is detected in the captured frame. If zero or multiple faces are found, return a validation error and abort.
  4. Call `DeepFace.represent(img_path=frame)` to calculate the face embedding vector.
  5. Save the resulting embedding vector in the database under `estudiantes.face_embedding`, alongside the student's `nombre` (name) and `codigo` (code).
