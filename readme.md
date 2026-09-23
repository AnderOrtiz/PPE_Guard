```
PPE_Guard/
├── app
│   ├── api
│   │   ├── v1
│   │   │   ├── endpoints
│   │   │   │   ├── __init__.py
│   │   │   │   └── health.py
│   │   │   ├── __init__.py
│   │   │   └── router.py
│   │   └── __init__.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── database.py
│   ├── models
│   │   └── __init__.py
│   ├── services
│   │   ├── __init__.py
│   │   └── compliance_service.py
│   ├── websockets
│   │   └── __init__.py
│   ├── __init__.py
│   └── main.py
├── compose.yaml
├── Dockerfile
├── readme.md
└── requirements.txt
```


````
hay que agregar que nos reunimos para hacer este comienzo del backend
```


[Repositorio de referencia](https://github.com/VoxDroid/Construction-Site-Safety-PPE-Detection)


```bash
conda activate yolo
uvicorn app.main:app --reload
```