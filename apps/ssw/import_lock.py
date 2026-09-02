from __future__ import annotations

"""Lock cross-processo simples para serializar a aplicação de relatórios SSW.

O Painel roda localmente em um único host. Um lock de arquivo impede que dois
processos (upload manual/worker do robô) apliquem simultaneamente o mesmo conjunto
de entidades e criem duplicidades por corrida. Não depende de pacote externo.
"""

import os
import time
from pathlib import Path

from django.conf import settings


class ImportBusyError(RuntimeError):
    pass


class SSWImportLock:
    def __init__(self, timeout: float | None = None, poll_interval: float = 0.20, lock_name: str = "ssw-import.lock"):
        configured = os.getenv("SSW_IMPORT_LOCK_TIMEOUT_SECONDS", "300")
        self.timeout = float(configured) if timeout is None else float(timeout)
        self.poll_interval = max(float(poll_interval), 0.05)
        self.path = Path(settings.BASE_DIR) / "local_data" / "locks" / lock_name
        self.handle = None
        self._locked = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        # O msvcrt.locking precisa que exista pelo menos um byte no arquivo.
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        deadline = time.monotonic() + max(self.timeout, 0)

        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.handle = handle
                self._locked = True
                return self
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    handle.close()
                    raise ImportBusyError(
                        "Já existe outra importação SSW aplicando dados. "
                        "Aguarde a execução atual terminar e tente novamente."
                    )
                time.sleep(self.poll_interval)

    def release(self):
        if not self.handle:
            return
        try:
            self.handle.seek(0)
            if self._locked:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._locked = False
            self.handle.close()
            self.handle = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
