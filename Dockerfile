# Imagen base con Python 3.12 slim (compatible con openpyxl, FastAPI, APScheduler)
FROM python:3.12-slim

# Directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del backend y frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Crear directorio de datos (base de datos SQLite)
RUN mkdir -p /app/backend/data

# Variables de entorno por defecto (sobrescribir con docker-compose o .env)
ENV PORT=8000
ENV DATABASE_PATH=/app/backend/data/comisiones.db
ENV AMBIENTE=production

# Puerto expuesto
EXPOSE 8000

# Directorio de trabajo del servidor
WORKDIR /app/backend

# Comando de arranque
CMD ["python", "main.py"]
