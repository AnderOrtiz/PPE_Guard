import signal

en_curso = False


def vigilar_senales():
    """uvicorn espera a que cierren las conexiones abiertas antes de correr el
    apagado del lifespan, y un stream MJPEG nunca cierra solo. Se anota la señal
    de apagado para que el stream corte y el servidor pueda liberar la cámara."""
    for senal in (signal.SIGINT, signal.SIGTERM):
        previo = signal.getsignal(senal)

        def manejador(signum, frame, previo=previo):
            global en_curso
            en_curso = True
            if callable(previo):
                previo(signum, frame)

        try:
            signal.signal(senal, manejador)
        except ValueError:
            pass  # fuera del hilo principal no se pueden registrar señales
