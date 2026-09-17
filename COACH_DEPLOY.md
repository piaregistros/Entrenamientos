# Entrenamientos Coach — despliegue CT105

El Coach está aislado del backend principal para reducir riesgo:

- FastAPI existente: `127.0.0.1:8000`
- Coach: `127.0.0.1:8001`
- Frontend Express/Vite: `0.0.0.0:3000`
- SQLite compartida: `/opt/entrenamiento/data/entrenamiento.db`

## 1. Backend

En CT105:

```bash
cd /opt/entrenamiento
git fetch origin
git checkout feature/coach-qwen-backend
git pull --ff-only origin feature/coach-qwen-backend
```

Crear `/opt/entrenamiento/.coach.env`:

```bash
QWEN_API_KEY=TU_CLAVE
QWEN_MODEL=qwen3.8-max
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Probar sintaxis:

```bash
python3 -m py_compile app/coach_routes.py coach_server.py
```

Instalar el servicio:

```bash
cp deploy/entrenamientos-coach.service /etc/systemd/system/entrenamientos-coach.service
systemctl daemon-reload
systemctl enable --now entrenamientos-coach.service
systemctl status entrenamientos-coach.service --no-pager
curl http://127.0.0.1:8001/health
```

## 2. Frontend

En CT105:

```bash
cd /opt/EntrenamientosAI
git fetch origin
git checkout feature/coach-qwen-frontend
git pull --ff-only origin feature/coach-qwen-frontend
npm ci
npm run lint
npm run build
systemctl restart entrenamiento-frontend.service
systemctl status entrenamiento-frontend.service --no-pager
```

El proxy existente conserva `/api/* -> 8000` y envía únicamente `/api/coach/* -> 8001`.

## 3. Comprobación final

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8001/health
curl -I http://127.0.0.1:3000/
```

Después abrir la aplicación normalmente. El usuario autenticado verá la pestaña **Coach**. La clave Qwen nunca llega al navegador.

## 4. Rollback seguro

Si el Coach falla, se puede detener y deshabilitar sin tocar el backend principal:

```bash
systemctl disable --now entrenamientos-coach.service
```

Y el frontend puede volver al commit anterior de `main` y reconstruirse. El servicio FastAPI principal en `8000` no depende del Coach.
