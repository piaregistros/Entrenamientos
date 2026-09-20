# Motor de dietas (feature/diet-engine)

No toca Coach ni la logica de entrenos. Solo anade `/api/diet`.

## Cablear en app/main.py (4 lineas)

```python
from .diet_routes import router as diet_router, init_diet_db
app.include_router(diet_router)
# dentro de startup(), despues de init_db():
init_diet_db()
```

Reglas: sin cerdo ni marisco; recetas 5-25 min; A/B/C = lun/mie/vie.
Objetivos: lose_fat, recomp, maintain, gain_muscle, performance.
