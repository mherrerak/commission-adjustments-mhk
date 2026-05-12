# Commission Manager
**Gestión de comisiones temporales para sellers y SKUs — Falabella Marketplace**

Aplicación web para registrar, monitorear y notificar cambios de comisiones temporales,
con generación automática de archivos Excel para carga en la plataforma interna.

---

## Características

- **Formulario** de carga con validaciones (solapamiento de fechas, duplicados)
- **Dashboard** de comisiones activas con indicadores de urgencia
- **Histórico** completo con filtros avanzados y exportación a Excel
- **Emails automáticos** al cargar una comisión (adjunta Entregable 1 y 2)
- **Cron diario** que detecta vencimientos y envía reversa (Entregable 3)
- **Aviso preventivo** configurable N días antes del vencimiento

---

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.12 + FastAPI |
| Base de datos | SQLite (via `sqlite3` estándar) |
| Email | `smtplib` (standard library) |
| Excel | `openpyxl` |
| Cron | `APScheduler` |
| Frontend | React 18 vía CDN + Babel Standalone |

---

## Instalación local (sin Docker)

### 1. Clonar / copiar el proyecto

```
commission-manager/
├── backend/
├── frontend/
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### 2. Crear entorno virtual e instalar dependencias

```bash
cd commission-manager/backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
# Copiar template
cp .env.example .env

# Editar .env con tus credenciales SMTP
```

Variables clave en `.env`:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SMTP_HOST` | Servidor SMTP | `smtp.gmail.com` |
| `SMTP_PORT` | Puerto SMTP | `587` |
| `SMTP_USER` | Cuenta de envío | `tu@gmail.com` |
| `SMTP_PASSWORD` | Contraseña / App Password | `xxxx xxxx xxxx` |
| `EMAIL_DESTINATARIO` | Receptor de notificaciones | `mherrerak@falabella.com` |
| `CRON_HORA_UTC` | Hora UTC del cron (7 AM Chile = 11 UTC) | `11` |
| `DIAS_AVISO_VENCIMIENTO` | Días de aviso preventivo | `2` |
| `RESPONSABLES` | Lista del equipo (separados por coma) | `Ana García,Carlos López` |

> **Gmail**: Activa la verificación en 2 pasos y crea una "App Password" en
> https://myaccount.google.com/apppasswords

### 4. Iniciar el servidor

```bash
# Desde commission-manager/backend/
python main.py
```

La aplicación estará en: **http://localhost:8000**

Documentación API: **http://localhost:8000/api/docs**

---

## Despliegue con Docker

```bash
# 1. Crear archivo .env en la raíz del proyecto
cp backend/.env.example .env
# Editar .env con tus credenciales

# 2. Levantar contenedor
docker-compose up -d

# 3. Ver logs
docker-compose logs -f commission-manager

# 4. Detener
docker-compose down
```

La base de datos SQLite se persiste en `./data/comisiones.db`.

---

## Archivos Excel generados

### Entregable 1 — Upload SKU
Carga de entidades en la plataforma.

| Columna | Valor |
|---------|-------|
| Entity Name | `commissionsku` |
| id | Código SKU |

### Entregable 2 — Upload SKU Value New
Asignación de nueva comisión.

| Columna | Valor |
|---------|-------|
| Attribute | `commissionsku` |
| B, C | (vacías) |
| commissionsku | Código SKU |
| Value | Nueva comisión (ej: 18.5) |

### Entregable 3 — Reversa SKU New
Reset de comisión (column Value vacía = eliminar comisión temporal).

| Columna | Valor |
|---------|-------|
| Attribute | `commissionsku` |
| B, C | (vacías) |
| commissionsku | Código SKU |
| Value | **(vacía)** |

> **Nota**: Si las columnas B y C tienen nombres específicos en el template de tu plataforma,
> actualízalos en `backend/services/excel_service.py` (líneas con el array `headers`).

---

## Flujo de notificaciones

```
[Usuario carga comisión]
    └─→ Backend guarda en BD
    └─→ Email enviado a mherrerak@falabella.com
          Asunto: "[Comisiones] Nueva carga - SKU 12345 - 11/05/2026"
          Adjunto 1: Upload_SKU_2026-05-11.xlsx
          Adjunto 2: Upload_SKU_Value_New_2026-05-11.xlsx

[Cron diario 7:00 AM Chile]
    └─→ Verifica comisiones vencidas
    └─→ Si hay vencidas → Email con Reversa
          Asunto: "⚠️ [Comisiones] SKUs con comisión VENCIDA - Acción requerida"
          Adjunto: Reversa_SKU_New_2026-05-11.xlsx
    └─→ Si hay por vencer (≤ N días) → Email de warning
          Asunto: "🔔 [Comisiones] 3 comisiones vencen en 2 día(s)"
```

---

## API REST

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/comisiones` | Crear nueva comisión |
| `GET` | `/api/comisiones` | Listar todas (filtros opcionales) |
| `GET` | `/api/comisiones/activas` | Solo las activas hoy |
| `GET` | `/api/comisiones/export` | Exportar a Excel |
| `PUT` | `/api/comisiones/{id}/anular` | Anular comisión |
| `GET` | `/api/stats` | Estadísticas del dashboard |
| `GET` | `/api/responsables` | Lista de responsables |
| `POST` | `/api/admin/revision-manual` | Forzar revisión del cron |

Documentación interactiva (Swagger): `/api/docs`

---

## Estructura del proyecto

```
commission-manager/
├── backend/
│   ├── main.py                    # Entry point FastAPI
│   ├── database.py                # SQLite setup y queries
│   ├── models.py                  # Pydantic models (validación)
│   ├── routes/
│   │   └── commissions.py         # Endpoints REST
│   ├── services/
│   │   ├── email_service.py       # Envío de emails SMTP
│   │   ├── excel_service.py       # Generación de archivos Excel
│   │   └── scheduler.py           # Cron job APScheduler
│   ├── data/                      # (creado automáticamente)
│   │   └── comisiones.db
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html                 # SPA React (CDN, sin build step)
│   └── styles.css
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Zona horaria y el cron

El scheduler corre en zona horaria `America/Santiago` (Chile), que ajusta automáticamente
según el horario de verano (DST).

| Variable | Valor por defecto | Equivalencia |
|----------|-------------------|--------------|
| `CRON_HORA_UTC` | `11` | 7:00 AM Chile (GMT-4) |
| `CRON_HORA_UTC` | `10` | 7:00 AM Chile (GMT-3, horario verano) |

Para forzar una ejecución manual sin esperar el cron:
```bash
curl -X POST http://localhost:8000/api/admin/revision-manual
```
