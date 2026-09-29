<div align="center">

# 🎓 Proyecto Plataforma Educativa

### Pipeline ETL para el análisis de progreso y abandono estudiantil

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white) ![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)

</div>

---

## 🎯 Descripción

Este proyecto implementa un **pipeline ETL** (Extract, Transform, Load) para analizar el **progreso y la tasa de abandono de estudiantes** en cursos online. Simula el flujo real de datos de una plataforma educativa: desde la generación de la información hasta su disponibilidad para análisis en una base de datos relacional.

## 🔄 Cómo funciona

```
Python  →  Genera y transforma los datos de estudiantes y cursos
   ↓
SQLite  →  Almacenamiento inicial / staging de los datos
   ↓
SQL     →  Integración y carga en MySQL para análisis
   ↓
MySQL   →  Base de datos relacional lista para consultas y reportes
```

1. **Generación de datos** — Python crea los datos de estudiantes, cursos y avance (o los procesa desde una fuente inicial).
2. **Staging en SQLite** — los datos se almacenan en una base ligera como paso intermedio.
3. **Integración en MySQL** — mediante SQL se migran e integran los datos en un modelo relacional.
4. **Análisis** — con la base ya integrada, se pueden calcular métricas de progreso y abandono por curso, cohorte o periodo.

## 🛠️ Tecnologías

| Categoría | Herramientas |
| :--- | :--- |
| **Lenguaje** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) |
| **Bases de datos** | ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white) ![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white) |
| **Proceso** | ETL (Extract, Transform, Load) |

## 📊 ¿Qué permite analizar?

- Progreso de los estudiantes a lo largo de los cursos.
- Tasa y momento de abandono (deserción) por curso.
- Base de datos integrada, lista para dashboards o reportes de seguimiento académico.

---

<div align="center">

**Lorena Theran** — Científica de Datos

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/lorenatheranfunez) [![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/lorefunez7-cpu)

</div>
