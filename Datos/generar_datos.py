"""
GENERADOR DE DATOS LOCAL - Plataforma de Educacion en Linea
============================================================

UN SOLO ARCHIVO, autocontenido: crea y actualiza una base de datos
SQLite local (un archivo .db en tu carpeta). No necesita servidor,
usuario ni contrasena. Esta es tu base de datos "fuente" (origen).

Mas adelante, con otro script aparte, migraremos estos datos hacia
tu MySQL (eso sera el ETL: Extract de este SQLite, Transform si hace
falta, Load hacia MySQL). Por ahora, este archivo solo se encarga de
generar los datos locales.

COMANDOS:

  1) Primera vez (una sola vez):
       python generar_datos.py inicializar

     Crea las tablas y siembra estudiantes, cursos, modulos, cohortes,
     inscripciones y el progreso inicial (todos en "no_iniciado").

  2) Cada dia (se puede correr todos los dias):
       python generar_datos.py cargar-dia

     Genera 1000 eventos de aprendizaje nuevos para el siguiente dia
     y actualiza el progreso de los estudiantes. NO borra nada de lo
     que ya existia, solo agrega el dia nuevo.

Requisitos: Python 3.9+, faker  ->  pip install faker
"""

import argparse
import csv
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

# ------------------------------------------------------------------
# CONFIGURACION
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "plataforma_educativa.db"
CSV_DIR = BASE_DIR / "csv_export"

TABLAS_EXPORTAR = [
    "ESTUDIANTE", "COHORTE", "CURSO", "MODULO",
    "INSCRIPCION", "PROGRESO_MODULO", "EVENTO_PROGRESO",
]

NUM_ESTUDIANTES = 400
NUM_COHORTES = 6
MODULOS_POR_CURSO = (4, 7)
FECHA_INICIO_SIMULACION = date.today()
EVENTOS_POR_DIA_DEFAULT = 1000

TEMAS_MODULO = [
    "Introduccion y objetivos", "Conceptos fundamentales", "Herramientas del entorno",
    "Practica guiada", "Casos de estudio", "Proyecto aplicado", "Evaluacion final",
    "Buenas practicas", "Automatizacion", "Integracion con otras herramientas",
]

CURSOS = [
    ("Python para Analisis de Datos", "Datos"),
    ("Fundamentos de SQL", "Datos"),
    ("Introduccion al Machine Learning", "Datos"),
    ("Desarrollo Web con JavaScript", "Programacion"),
    ("Fundamentos de Programacion en Python", "Programacion"),
    ("Estructuras de Datos y Algoritmos", "Programacion"),
    ("Diseno de Experiencia de Usuario (UX)", "Diseno"),
    ("Diseno Grafico Digital", "Diseno"),
    ("Marketing Digital", "Negocios"),
    ("Gestion de Proyectos Agiles", "Negocios"),
    ("Excel Avanzado para Negocios", "Negocios"),
    ("Ciberseguridad Basica", "Tecnologia"),
]

fake = Faker("es_ES")
random.seed(42)
Faker.seed(42)

# ------------------------------------------------------------------
# ESQUEMA (embebido: no depende de un archivo externo)
# ------------------------------------------------------------------
ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS ESTUDIANTE (
    id_estudiante   INTEGER PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    apellido        VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    fecha_registro  DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS COHORTE (
    id_cohorte    INTEGER PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    fecha_inicio  DATE NOT NULL,
    fecha_fin     DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS CURSO (
    id_curso        INTEGER PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    descripcion     VARCHAR(500),
    categoria       VARCHAR(100),
    fecha_creacion  DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS MODULO (
    id_modulo        INTEGER PRIMARY KEY,
    id_curso         INT NOT NULL,
    nombre           VARCHAR(150) NOT NULL,
    orden            INT NOT NULL,
    descripcion      VARCHAR(500),
    duracion_horas   INT,
    FOREIGN KEY (id_curso) REFERENCES CURSO(id_curso)
);

CREATE TABLE IF NOT EXISTS INSCRIPCION (
    id_inscripcion            INTEGER PRIMARY KEY,
    id_estudiante             INT NOT NULL,
    id_curso                  INT NOT NULL,
    id_cohorte                INT NOT NULL,
    fecha_inscripcion         DATE NOT NULL,
    estado_curso              VARCHAR(20) NOT NULL,
    porcentaje_avance_curso   DECIMAL(5,2) DEFAULT 0,
    FOREIGN KEY (id_estudiante) REFERENCES ESTUDIANTE(id_estudiante),
    FOREIGN KEY (id_curso) REFERENCES CURSO(id_curso),
    FOREIGN KEY (id_cohorte) REFERENCES COHORTE(id_cohorte)
);

CREATE TABLE IF NOT EXISTS PROGRESO_MODULO (
    id_progreso_modulo        INTEGER PRIMARY KEY,
    id_inscripcion            INT NOT NULL,
    id_modulo                 INT NOT NULL,
    estado_modulo             VARCHAR(20) NOT NULL,
    porcentaje_avance_modulo  DECIMAL(5,2) DEFAULT 0,
    fecha_actualizacion       DATE,
    FOREIGN KEY (id_inscripcion) REFERENCES INSCRIPCION(id_inscripcion),
    FOREIGN KEY (id_modulo) REFERENCES MODULO(id_modulo)
);

CREATE TABLE IF NOT EXISTS EVENTO_PROGRESO (
    id_evento            INTEGER PRIMARY KEY,
    id_progreso_modulo   INT NOT NULL,
    tipo_evento          VARCHAR(30) NOT NULL,
    fecha_evento         DATE NOT NULL,
    detalle              VARCHAR(255),
    FOREIGN KEY (id_progreso_modulo) REFERENCES PROGRESO_MODULO(id_progreso_modulo)
);

CREATE TABLE IF NOT EXISTS etl_control (
    id_ejecucion       INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_dato_cargado DATE UNIQUE NOT NULL,
    fecha_ejecucion    TEXT NOT NULL,
    eventos_cargados   INT NOT NULL
);
"""


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def tiene_datos(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ESTUDIANTE'")
    if cur.fetchone() is None:
        return False
    return conn.execute("SELECT COUNT(*) FROM ESTUDIANTE").fetchone()[0] > 0


# ============================================================
# COMANDO: inicializar
# ============================================================
def inicializar(conn: sqlite3.Connection) -> None:
    if tiene_datos(conn):
        print("Ya existen datos en esta base. 'inicializar' solo se corre una vez.")
        print(f"Si quieres empezar de cero, borra el archivo {DB_PATH.name} y vuelve a correr este comando.")
        return

    print("=== Creando tablas ===")
    conn.executescript(ESQUEMA_SQL)
    conn.commit()

    print("=== Sembrando dimensiones ===")
    ids_estudiante = _poblar_estudiantes(conn, NUM_ESTUDIANTES)
    cohortes = _poblar_cohortes(conn, NUM_COHORTES)
    ids_curso = _poblar_cursos(conn)
    modulos_por_curso = _poblar_modulos(conn, ids_curso)

    print("=== Creando inscripciones y progreso inicial ===")
    _poblar_inscripciones_y_progreso(conn, ids_estudiante, ids_curso, cohortes, modulos_por_curso)

    print(f"\nListo. Base creada en: {DB_PATH}")
    print("A partir de ahora corre: python generar_datos.py cargar-dia")


def _poblar_estudiantes(conn, n):
    filas = []
    for i in range(1, n + 1):
        nombre, apellido = fake.first_name(), fake.last_name()
        email = f"{nombre.lower()}.{apellido.lower()}{i}@correo.com".replace(" ", "")
        fecha_registro = fake.date_between(start_date=date(2024, 1, 1), end_date=FECHA_INICIO_SIMULACION)
        filas.append((i, nombre, apellido, email, fecha_registro.isoformat()))
    conn.executemany(
        "INSERT INTO ESTUDIANTE (id_estudiante, nombre, apellido, email, fecha_registro) VALUES (?,?,?,?,?)",
        filas,
    )
    conn.commit()
    print(f"  ESTUDIANTE: {len(filas)} filas")
    return [f[0] for f in filas]


def _poblar_cohortes(conn, n):
    filas = []
    inicio = FECHA_INICIO_SIMULACION - timedelta(days=180)
    for i in range(1, n + 1):
        f_inicio = inicio + timedelta(days=30 * i)
        f_fin = f_inicio + timedelta(days=90)
        nombre = f"Cohorte {f_inicio.strftime('%Y')}-{((f_inicio.month - 1)//3)+1}-{i}"
        filas.append((i, nombre, f_inicio.isoformat(), f_fin.isoformat()))
    conn.executemany(
        "INSERT INTO COHORTE (id_cohorte, nombre, fecha_inicio, fecha_fin) VALUES (?,?,?,?)", filas
    )
    conn.commit()
    print(f"  COHORTE: {len(filas)} filas")
    return filas


def _poblar_cursos(conn):
    filas = []
    for i, (nombre, categoria) in enumerate(CURSOS, start=1):
        descripcion = fake.sentence(nb_words=12)
        fecha_creacion = fake.date_between(
            start_date=FECHA_INICIO_SIMULACION - timedelta(days=730),
            end_date=FECHA_INICIO_SIMULACION - timedelta(days=200),
        )
        filas.append((i, nombre, descripcion, categoria, fecha_creacion.isoformat()))
    conn.executemany(
        "INSERT INTO CURSO (id_curso, nombre, descripcion, categoria, fecha_creacion) VALUES (?,?,?,?,?)",
        filas,
    )
    conn.commit()
    print(f"  CURSO: {len(filas)} filas")
    return [f[0] for f in filas]


def _poblar_modulos(conn, ids_curso):
    filas, modulos_por_curso, id_modulo = [], {}, 1
    for id_curso in ids_curso:
        n = random.randint(*MODULOS_POR_CURSO)
        modulos_por_curso[id_curso] = []
        for orden in range(1, n + 1):
            nombre = f"Modulo {orden}: {random.choice(TEMAS_MODULO)}"
            descripcion = fake.sentence(nb_words=10)
            duracion = random.choice([2, 3, 4, 5, 6, 8])
            filas.append((id_modulo, id_curso, nombre, orden, descripcion, duracion))
            modulos_por_curso[id_curso].append(id_modulo)
            id_modulo += 1
    conn.executemany(
        "INSERT INTO MODULO (id_modulo, id_curso, nombre, orden, descripcion, duracion_horas) VALUES (?,?,?,?,?,?)",
        filas,
    )
    conn.commit()
    print(f"  MODULO: {len(filas)} filas")
    return modulos_por_curso


def _cohorte_para_fecha(cohortes, fecha):
    for id_cohorte, _n, f_inicio, f_fin in cohortes:
        if date.fromisoformat(f_inicio) <= fecha <= date.fromisoformat(f_fin):
            return id_cohorte
    return random.choice(cohortes)[0]


def _poblar_inscripciones_y_progreso(conn, ids_estudiante, ids_curso, cohortes, modulos_por_curso):
    inscripciones, progresos = [], []
    id_inscripcion = id_progreso = 1
    for id_estudiante in ids_estudiante:
        for id_curso in random.sample(ids_curso, k=random.randint(1, 3)):
            fecha_inscripcion = fake.date_between(
                start_date=FECHA_INICIO_SIMULACION - timedelta(days=150),
                end_date=FECHA_INICIO_SIMULACION - timedelta(days=1),
            )
            id_cohorte = _cohorte_para_fecha(cohortes, fecha_inscripcion)
            inscripciones.append((id_inscripcion, id_estudiante, id_curso, id_cohorte,
                                   fecha_inscripcion.isoformat(), "en_curso", 0.0))
            for id_modulo in modulos_por_curso[id_curso]:
                progresos.append((id_progreso, id_inscripcion, id_modulo,
                                   "no_iniciado", 0.0, fecha_inscripcion.isoformat()))
                id_progreso += 1
            id_inscripcion += 1

    conn.executemany(
        "INSERT INTO INSCRIPCION (id_inscripcion, id_estudiante, id_curso, id_cohorte, "
        "fecha_inscripcion, estado_curso, porcentaje_avance_curso) VALUES (?,?,?,?,?,?,?)",
        inscripciones,
    )
    conn.executemany(
        "INSERT INTO PROGRESO_MODULO (id_progreso_modulo, id_inscripcion, id_modulo, "
        "estado_modulo, porcentaje_avance_modulo, fecha_actualizacion) VALUES (?,?,?,?,?,?)",
        progresos,
    )
    conn.commit()
    print(f"  INSCRIPCION: {len(inscripciones)} filas")
    print(f"  PROGRESO_MODULO: {len(progresos)} filas")


# ============================================================
# COMANDO: cargar-dia
# ============================================================
def _siguiente_estado(estado_actual: str):
    if estado_actual == "no_iniciado":
        return "iniciado", "en_progreso"
    if estado_actual == "en_progreso":
        r = random.random()
        if r < 0.55:
            return "en_progreso", "en_progreso"
        elif r < 0.75:
            return "pausado", "en_progreso"
        elif r < 0.95:
            return "completado", "completado"
        else:
            return "abandonado", "abandonado"
    return "en_progreso", estado_actual


def cargar_dia(conn: sqlite3.Connection, eventos_por_dia: int, fecha_forzada: str | None) -> None:
    if not tiene_datos(conn):
        print("No hay datos base todavia. Corre primero: python generar_datos.py inicializar")
        return

    if fecha_forzada:
        fecha_a_cargar = date.fromisoformat(fecha_forzada)
    else:
        ultima = conn.execute("SELECT MAX(fecha_dato_cargado) FROM etl_control").fetchone()[0]
        fecha_a_cargar = (
            FECHA_INICIO_SIMULACION if ultima is None
            else date.fromisoformat(ultima) + timedelta(days=1)
        )

    ya_cargado = conn.execute(
        "SELECT 1 FROM etl_control WHERE fecha_dato_cargado = ?", (fecha_a_cargar.isoformat(),)
    ).fetchone()
    if ya_cargado:
        print(f"El dia {fecha_a_cargar.isoformat()} ya fue cargado antes. No se duplica nada.")
        return

    cur = conn.cursor()
    filas = cur.execute(
        "SELECT id_progreso_modulo, estado_modulo, porcentaje_avance_modulo FROM PROGRESO_MODULO"
    ).fetchall()
    ids_progreso = [f[0] for f in filas]
    estado_por_progreso = {f[0]: f[1] for f in filas}
    porcentaje_por_progreso = {f[0]: f[2] for f in filas}

    siguiente_id_evento = (cur.execute("SELECT MAX(id_evento) FROM EVENTO_PROGRESO").fetchone()[0] or 0) + 1

    eventos, actualizaciones = [], []
    for _ in range(eventos_por_dia):
        id_progreso = random.choice(ids_progreso)
        estado_actual = estado_por_progreso[id_progreso]
        tipo_evento, nuevo_estado = _siguiente_estado(estado_actual)

        detalle = None
        if tipo_evento == "abandonado":
            detalle = "Sin actividad posterior registrada"
        elif tipo_evento == "completado":
            detalle = "Modulo finalizado por el estudiante"

        eventos.append((siguiente_id_evento, id_progreso, tipo_evento, fecha_a_cargar.isoformat(), detalle))
        siguiente_id_evento += 1

        pct = porcentaje_por_progreso[id_progreso]
        if tipo_evento == "iniciado":
            pct = 10.0
        elif tipo_evento == "en_progreso":
            pct = min(95.0, pct + random.uniform(10, 25))
        elif tipo_evento == "completado":
            pct = 100.0

        estado_por_progreso[id_progreso] = nuevo_estado
        porcentaje_por_progreso[id_progreso] = pct
        actualizaciones.append((nuevo_estado, round(pct, 2), fecha_a_cargar.isoformat(), id_progreso))

    cur.executemany(
        "INSERT INTO EVENTO_PROGRESO (id_evento, id_progreso_modulo, tipo_evento, fecha_evento, detalle) "
        "VALUES (?,?,?,?,?)",
        eventos,
    )
    cur.executemany(
        "UPDATE PROGRESO_MODULO SET estado_modulo=?, porcentaje_avance_modulo=?, fecha_actualizacion=? "
        "WHERE id_progreso_modulo=?",
        actualizaciones,
    )

    _actualizar_avance_inscripciones(conn)

    cur.execute(
        "INSERT INTO etl_control (fecha_dato_cargado, fecha_ejecucion, eventos_cargados) VALUES (?,?,?)",
        (fecha_a_cargar.isoformat(), date.today().isoformat(), len(eventos)),
    )
    conn.commit()
    print(f"Dia {fecha_a_cargar.isoformat()}: {len(eventos)} eventos cargados (sin borrar datos previos).")


def _actualizar_avance_inscripciones(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    filas = cur.execute(
        """
        SELECT i.id_inscripcion,
               AVG(pm.porcentaje_avance_modulo),
               SUM(CASE WHEN pm.estado_modulo='completado' THEN 1 ELSE 0 END),
               SUM(CASE WHEN pm.estado_modulo='abandonado' THEN 1 ELSE 0 END),
               COUNT(*)
        FROM INSCRIPCION i
        JOIN PROGRESO_MODULO pm ON pm.id_inscripcion = i.id_inscripcion
        GROUP BY i.id_inscripcion
        """
    ).fetchall()
    actualizaciones = []
    for id_inscripcion, avg_pct, completados, abandonados, total in filas:
        avg_pct = avg_pct or 0.0
        if completados == total:
            estado = "completado"
        elif abandonados > 0 and completados == 0:
            estado = "abandonado"
        else:
            estado = "en_curso"
        actualizaciones.append((round(avg_pct, 2), estado, id_inscripcion))
    cur.executemany(
        "UPDATE INSCRIPCION SET porcentaje_avance_curso=?, estado_curso=? WHERE id_inscripcion=?",
        actualizaciones,
    )
    conn.commit()


# ============================================================
# COMANDO: exportar-csv
# ============================================================
def exportar_csv(conn: sqlite3.Connection) -> None:
    """Vuelca cada tabla completa a un .csv (con encabezado). No decide
    nada de negocio: la integracion/upsert hacia MySQL la hace el script
    SQL (etl_integracion.sql), no este export."""
    if not tiene_datos(conn):
        print("No hay datos todavia. Corre primero: python generar_datos.py inicializar")
        return

    CSV_DIR.mkdir(exist_ok=True)
    conn.row_factory = sqlite3.Row
    for tabla in TABLAS_EXPORTAR:
        filas = conn.execute(f"SELECT * FROM {tabla}").fetchall()
        ruta = CSV_DIR / f"{tabla}.csv"
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            if filas:
                writer.writerow(filas[0].keys())
                writer.writerows(tuple(f) for f in filas)
            else:
                writer.writerow([d[0] for d in conn.execute(f"SELECT * FROM {tabla} LIMIT 0").description])
        print(f"  {tabla}: {len(filas)} filas -> {ruta.name}")

    print(f"\nCSVs listos en: {CSV_DIR}")
    print("Ahora corre etl_integracion.sql contra tu MySQL para integrarlos.")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Generador de datos local - Plataforma educativa")
    parser.add_argument("accion", choices=["inicializar", "cargar-dia", "exportar-csv"])
    parser.add_argument("--eventos-por-dia", type=int, default=EVENTOS_POR_DIA_DEFAULT)
    parser.add_argument("--fecha", type=str, default=None, help="Forzar una fecha especifica (YYYY-MM-DD)")
    args = parser.parse_args()

    conn = conectar()
    if args.accion == "inicializar":
        inicializar(conn)
    elif args.accion == "cargar-dia":
        cargar_dia(conn, args.eventos_por_dia, args.fecha)
    elif args.accion == "exportar-csv":
        exportar_csv(conn)
    conn.close()


if __name__ == "__main__":
    main()
