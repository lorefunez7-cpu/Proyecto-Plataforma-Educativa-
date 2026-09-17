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

  3) Solo si EVENTO_PROGRESO local se vacio y sus id_evento volvieron a
     empezar desde 1 (por ejemplo, si se borraron filas a mano):
       python generar_datos.py resincronizar-eventos --offset <numero>

     <numero> = el id_evento mas alto que ya tengas cargado en MySQL
     (SELECT MAX(id_evento) FROM EVENTO_PROGRESO; alla). Esto evita que
     el ETL ignore los eventos nuevos por chocar con ids ya subidos.

Requisitos: Python 3.9+, faker  ->  pip install faker
"""

import argparse
import csv
import random
import sqlite3
from datetime import date, datetime, timedelta
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

# Cada dia, ademas de avanzar el progreso existente, algunos estudiantes se
# inscriben en un curso nuevo (que todavia no han tomado). Esto evita que la
# simulacion se "seque" cuando todas las inscripciones existentes ya
# completaron su curso o quedaron congeladas por abandono.
MAX_CURSOS_POR_ESTUDIANTE = 4
NUEVAS_INSCRIPCIONES_POR_DIA = (2, 6)  # rango aleatorio de nuevas inscripciones por dia

# Ademas, cada dia se registran estudiantes nuevos (gente que nunca habia
# usado la plataforma), tal como pasa en la realidad. Esto es lo que evita
# que la simulacion tenga techo: sin estudiantes nuevos, el mecanismo de
# "nuevas inscripciones" tambien se termina agotando cuando todos los
# estudiantes existentes llegan a MAX_CURSOS_POR_ESTUDIANTE.
NUEVOS_ESTUDIANTES_POR_DIA = (0, 3)  # rango aleatorio de estudiantes nuevos por dia

# Cada cohorte tiene un cupo maximo de inscripciones. Cuando la cohorte
# "activa" (la mas reciente) llega a su cupo, se abre una cohorte nueva
# automaticamente para que las inscripciones sigan cayendo en algun lado.
CUPO_MAXIMO_POR_COHORTE = 200

# Probabilidad, cada dia, de que se lance un curso nuevo (tomado de
# CURSOS_FUTUROS). No todos los dias sale un curso nuevo en una plataforma
# real, por eso es una probabilidad baja y no una cantidad fija.
PROBABILIDAD_CURSO_NUEVO_POR_DIA = 0.08

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

# Cursos que la plataforma todavia no ofrece, pero que puede llegar a
# lanzar mas adelante. cargar-dia los va agregando de a uno, de vez en
# cuando (ver PROBABILIDAD_CURSO_NUEVO_POR_DIA), para que el catalogo
# tambien pueda seguir creciendo en vez de quedarse fijo en los 12 de
# CURSOS de arriba.
CURSOS_FUTUROS = [
    ("Introduccion a la Inteligencia Artificial", "Datos"),
    ("Visualizacion de Datos con Power BI", "Datos"),
    ("Desarrollo de Aplicaciones Moviles", "Programacion"),
    ("Backend con Node.js", "Programacion"),
    ("Diseno de Producto Digital", "Diseno"),
    ("Animacion y Motion Graphics", "Diseno"),
    ("Redes Sociales y Contenido Digital", "Negocios"),
    ("Finanzas Personales", "Negocios"),
    ("Cloud Computing Basico", "Tecnologia"),
    ("Fundamentos de DevOps", "Tecnologia"),
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
    fecha_fin     DATE NOT NULL,
    cupo_maximo   INTEGER
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


def _migrar_esquema(conn: sqlite3.Connection) -> None:
    """Agrega columnas nuevas a bases creadas con una version anterior de
    este script, sin borrar ni tocar los datos que ya existen."""
    columnas = [f[1] for f in conn.execute("PRAGMA table_info(COHORTE)").fetchall()]
    if "cupo_maximo" not in columnas:
        conn.execute("ALTER TABLE COHORTE ADD COLUMN cupo_maximo INTEGER")
        conn.execute(
            "UPDATE COHORTE SET cupo_maximo = ? WHERE cupo_maximo IS NULL",
            (CUPO_MAXIMO_POR_COHORTE,),
        )
        conn.commit()
        print(f"  (migracion) Se agrego COHORTE.cupo_maximo = {CUPO_MAXIMO_POR_COHORTE} a las cohortes existentes.")


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
    # Todas las cohortes, desde el inicio, respetan el mismo cupo_maximo
    # real (CUPO_MAXIMO_POR_COHORTE). La siembra inicial de inscripciones
    # (mas abajo, en _poblar_inscripciones_y_progreso) tambien respeta este
    # cupo, asi que ninguna cohorte queda con mas inscritos de los que
    # declara poder tener.
    filas = []
    inicio = FECHA_INICIO_SIMULACION - timedelta(days=180)
    for i in range(1, n + 1):
        f_inicio = inicio + timedelta(days=30 * i)
        f_fin = f_inicio + timedelta(days=90)
        nombre = f"Cohorte {f_inicio.strftime('%Y')}-{((f_inicio.month - 1)//3)+1}-{i}"
        filas.append((i, nombre, f_inicio.isoformat(), f_fin.isoformat(), CUPO_MAXIMO_POR_COHORTE))
    conn.executemany(
        "INSERT INTO COHORTE (id_cohorte, nombre, fecha_inicio, fecha_fin, cupo_maximo) VALUES (?,?,?,?,?)", filas
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


def _cohorte_con_cupo(cohortes, fecha, ocupacion):
    """Elige la cohorte mas cercana en fecha a 'fecha_inscripcion' que
    todavia tenga cupo disponible (respeta cupo_maximo). Si la cohorte
    "natural" (por rango de fechas) ya esta llena, el estudiante cae en la
    siguiente cohorte mas cercana con espacio -- asi ninguna cohorte queda
    nunca con mas inscritos de los que su cupo_maximo permite."""
    candidatas = sorted(
        cohortes,
        key=lambda c: abs((date.fromisoformat(c[2]) - fecha).days),
    )
    for fila in candidatas:
        id_cohorte, cupo_max = fila[0], fila[4]
        if cupo_max is None or ocupacion.get(id_cohorte, 0) < cupo_max:
            return id_cohorte
    # No deberia pasar (NUM_COHORTES * CUPO_MAXIMO_POR_COHORTE alcanza para
    # todos los estudiantes), pero por seguridad cae en la que tenga mas
    # espacio relativo en vez de reventar.
    return min(cohortes, key=lambda c: ocupacion.get(c[0], 0))[0]


def _poblar_inscripciones_y_progreso(conn, ids_estudiante, ids_curso, cohortes, modulos_por_curso):
    inscripciones, progresos = [], []
    id_inscripcion = id_progreso = 1
    ocupacion_cohorte = {fila[0]: 0 for fila in cohortes}
    for id_estudiante in ids_estudiante:
        for id_curso in random.sample(ids_curso, k=random.randint(1, 3)):
            fecha_inscripcion = fake.date_between(
                start_date=FECHA_INICIO_SIMULACION - timedelta(days=150),
                end_date=FECHA_INICIO_SIMULACION - timedelta(days=1),
            )
            id_cohorte = _cohorte_con_cupo(cohortes, fecha_inscripcion, ocupacion_cohorte)
            ocupacion_cohorte[id_cohorte] += 1
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

    _migrar_esquema(conn)

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

    # Progreso de cada modulo junto con su 'orden' dentro del curso. Esto es
    # clave: el aprendizaje debe respetar la secuencia (no tiene sentido que
    # el modulo 3 este en curso si el modulo 1 nunca se empezo). Por eso el
    # "modulo activo" de cada inscripcion es siempre el primero, en orden,
    # que todavia no esta completado.
    filas = cur.execute(
        """
        SELECT pm.id_progreso_modulo, pm.id_inscripcion, pm.estado_modulo,
               pm.porcentaje_avance_modulo, m.orden
        FROM PROGRESO_MODULO pm
        JOIN MODULO m ON m.id_modulo = pm.id_modulo
        ORDER BY pm.id_inscripcion, m.orden
        """
    ).fetchall()

    estado_por_progreso = {}
    porcentaje_por_progreso = {}
    secuencia_por_inscripcion: dict[int, list[int]] = {}
    for id_progreso, id_inscripcion, estado, pct, _orden in filas:
        estado_por_progreso[id_progreso] = estado
        porcentaje_por_progreso[id_progreso] = pct
        secuencia_por_inscripcion.setdefault(id_inscripcion, []).append(id_progreso)

    # indice_activo[id_inscripcion] = posicion (en la secuencia de modulos)
    # del modulo que esa inscripcion esta cursando ahora mismo.
    # Si ese modulo activo queda 'abandonado', la inscripcion se congela ahi
    # (no se le generan mas eventos): asi el modulo donde se estanco queda
    # registrado de forma clara y permanente, en vez de ser aleatorio.
    indice_activo: dict[int, int] = {}
    pool_activo: list[int] = []
    for id_inscripcion, secuencia in secuencia_por_inscripcion.items():
        idx = len(secuencia)
        for pos, id_progreso in enumerate(secuencia):
            if estado_por_progreso[id_progreso] != "completado":
                idx = pos
                break
        indice_activo[id_inscripcion] = idx
        if idx < len(secuencia) and estado_por_progreso[secuencia[idx]] != "abandonado":
            pool_activo.append(id_inscripcion)

    # ------------------------------------------------------------
    # NUEVAS INSCRIPCIONES DEL DIA
    # Algunos estudiantes se inscriben en un curso nuevo que no han
    # tomado. Sin esto, una vez que todas las inscripciones existentes
    # terminan (completan o se estancan), no queda nada que avanzar y
    # cargar-dia deja de generar actividad.
    # ------------------------------------------------------------
    modulos_por_curso_actual: dict[int, list[int]] = {}
    for id_modulo, id_curso, _orden in cur.execute(
        "SELECT id_modulo, id_curso, orden FROM MODULO ORDER BY id_curso, orden"
    ).fetchall():
        modulos_por_curso_actual.setdefault(id_curso, []).append(id_modulo)

    todos_los_cursos = list(modulos_por_curso_actual.keys())

    # ------------------------------------------------------------
    # CURSO NUEVO (ocasional)
    # De vez en cuando el catalogo crece con un curso nuevo (tomado de
    # CURSOS_FUTUROS), con sus propios modulos. Asi el catalogo no se queda
    # fijo en los 12 cursos iniciales para siempre. Cuando ya no queda
    # ningun curso pendiente en CURSOS_FUTUROS, este mecanismo simplemente
    # deja de generar cursos (el resto de la simulacion sigue igual).
    # ------------------------------------------------------------
    nombres_curso_existentes = {n for (n,) in cur.execute("SELECT nombre FROM CURSO").fetchall()}
    catalogo_pendiente = [c for c in CURSOS_FUTUROS if c[0] not in nombres_curso_existentes]

    cursos_nuevos, modulos_de_cursos_nuevos = [], []
    if catalogo_pendiente and random.random() < PROBABILIDAD_CURSO_NUEVO_POR_DIA:
        nombre_curso_nuevo, categoria_curso_nueva = catalogo_pendiente[0]
        id_curso_nuevo = (cur.execute("SELECT MAX(id_curso) FROM CURSO").fetchone()[0] or 0) + 1
        descripcion_curso_nuevo = fake.sentence(nb_words=12)
        cursos_nuevos.append((
            id_curso_nuevo, nombre_curso_nuevo, descripcion_curso_nuevo,
            categoria_curso_nueva, fecha_a_cargar.isoformat(),
        ))

        id_modulo_nuevo = (cur.execute("SELECT MAX(id_modulo) FROM MODULO").fetchone()[0] or 0) + 1
        modulos_del_curso_nuevo = []
        for orden in range(1, random.randint(*MODULOS_POR_CURSO) + 1):
            nombre_modulo_nuevo = f"Modulo {orden}: {random.choice(TEMAS_MODULO)}"
            descripcion_modulo_nuevo = fake.sentence(nb_words=10)
            duracion_modulo_nuevo = random.choice([2, 3, 4, 5, 6, 8])
            modulos_de_cursos_nuevos.append((
                id_modulo_nuevo, id_curso_nuevo, nombre_modulo_nuevo,
                orden, descripcion_modulo_nuevo, duracion_modulo_nuevo,
            ))
            modulos_del_curso_nuevo.append(id_modulo_nuevo)
            id_modulo_nuevo += 1

        modulos_por_curso_actual[id_curso_nuevo] = modulos_del_curso_nuevo
        todos_los_cursos.append(id_curso_nuevo)

        cur.executemany(
            "INSERT INTO CURSO (id_curso, nombre, descripcion, categoria, fecha_creacion) VALUES (?,?,?,?,?)",
            cursos_nuevos,
        )
        cur.executemany(
            "INSERT INTO MODULO (id_modulo, id_curso, nombre, orden, descripcion, duracion_horas) VALUES (?,?,?,?,?,?)",
            modulos_de_cursos_nuevos,
        )

    cursos_por_estudiante: dict[int, set] = {}
    for id_estudiante, id_curso in cur.execute(
        "SELECT id_estudiante, id_curso FROM INSCRIPCION"
    ).fetchall():
        cursos_por_estudiante.setdefault(id_estudiante, set()).add(id_curso)

    todos_los_estudiantes = [
        f[0] for f in cur.execute("SELECT id_estudiante FROM ESTUDIANTE").fetchall()
    ]

    # ------------------------------------------------------------
    # ESTUDIANTES NUEVOS DEL DIA
    # En la realidad la plataforma sigue recibiendo gente que se registra
    # por primera vez, no solo estudiantes que ya estaban. Se agregan aqui,
    # antes de generar las inscripciones nuevas, para que puedan inscribirse
    # ese mismo dia.
    # ------------------------------------------------------------
    siguiente_id_estudiante = (cur.execute("SELECT MAX(id_estudiante) FROM ESTUDIANTE").fetchone()[0] or 0) + 1
    nuevos_estudiantes = []
    n_nuevos_estudiantes = random.randint(*NUEVOS_ESTUDIANTES_POR_DIA)
    for _ in range(n_nuevos_estudiantes):
        nombre, apellido = fake.first_name(), fake.last_name()
        id_estudiante = siguiente_id_estudiante
        email = f"{nombre.lower()}.{apellido.lower()}{id_estudiante}@correo.com".replace(" ", "")
        nuevos_estudiantes.append((id_estudiante, nombre, apellido, email, fecha_a_cargar.isoformat()))
        todos_los_estudiantes.append(id_estudiante)
        siguiente_id_estudiante += 1

    if nuevos_estudiantes:
        cur.executemany(
            "INSERT INTO ESTUDIANTE (id_estudiante, nombre, apellido, email, fecha_registro) VALUES (?,?,?,?,?)",
            nuevos_estudiantes,
        )

    # ------------------------------------------------------------
    # COHORTE ACTIVA (con cupo) para las inscripciones nuevas de hoy.
    # Se usa la cohorte mas reciente mientras tenga espacio; en cuanto
    # llega a su cupo_maximo se abre una cohorte nueva automaticamente.
    # ------------------------------------------------------------
    id_cohorte_activa, _nombre_c, _f_ini_c, _f_fin_c, cupo_maximo_activa = cur.execute(
        "SELECT id_cohorte, nombre, fecha_inicio, fecha_fin, cupo_maximo FROM COHORTE ORDER BY id_cohorte DESC LIMIT 1"
    ).fetchone()
    ocupacion_cohorte_activa = cur.execute(
        "SELECT COUNT(*) FROM INSCRIPCION WHERE id_cohorte = ?", (id_cohorte_activa,)
    ).fetchone()[0]
    cohortes_nuevas = []

    siguiente_id_inscripcion = (cur.execute("SELECT MAX(id_inscripcion) FROM INSCRIPCION").fetchone()[0] or 0) + 1
    siguiente_id_progreso = (cur.execute("SELECT MAX(id_progreso_modulo) FROM PROGRESO_MODULO").fetchone()[0] or 0) + 1

    nuevas_inscripciones, nuevos_progresos_iniciales = [], []
    n_nuevas = random.randint(*NUEVAS_INSCRIPCIONES_POR_DIA)
    for _ in range(n_nuevas):
        candidatos = [
            e for e in todos_los_estudiantes
            if len(cursos_por_estudiante.get(e, set())) < MAX_CURSOS_POR_ESTUDIANTE
            and len(cursos_por_estudiante.get(e, set())) < len(todos_los_cursos)
        ]
        if not candidatos:
            break  # ya nadie puede tomar mas cursos

        id_estudiante = random.choice(candidatos)
        cursos_disponibles = [c for c in todos_los_cursos if c not in cursos_por_estudiante.get(id_estudiante, set())]
        id_curso = random.choice(cursos_disponibles)
        cursos_por_estudiante.setdefault(id_estudiante, set()).add(id_curso)

        if cupo_maximo_activa is not None and ocupacion_cohorte_activa >= cupo_maximo_activa:
            id_cohorte_activa += 1
            f_inicio_nueva = fecha_a_cargar
            f_fin_nueva = fecha_a_cargar + timedelta(days=90)
            nombre_nueva = (
                f"Cohorte {f_inicio_nueva.strftime('%Y')}-"
                f"{((f_inicio_nueva.month - 1)//3)+1}-{id_cohorte_activa}"
            )
            cupo_maximo_activa = CUPO_MAXIMO_POR_COHORTE
            cohortes_nuevas.append((
                id_cohorte_activa, nombre_nueva, f_inicio_nueva.isoformat(),
                f_fin_nueva.isoformat(), cupo_maximo_activa,
            ))
            ocupacion_cohorte_activa = 0

        id_cohorte = id_cohorte_activa
        ocupacion_cohorte_activa += 1
        id_inscripcion = siguiente_id_inscripcion
        siguiente_id_inscripcion += 1
        nuevas_inscripciones.append((
            id_inscripcion, id_estudiante, id_curso, id_cohorte,
            fecha_a_cargar.isoformat(), "en_curso", 0.0,
        ))

        secuencia = []
        for id_modulo in modulos_por_curso_actual[id_curso]:
            id_progreso = siguiente_id_progreso
            siguiente_id_progreso += 1
            nuevos_progresos_iniciales.append((
                id_progreso, id_inscripcion, id_modulo,
                "no_iniciado", 0.0, fecha_a_cargar.isoformat(),
            ))
            estado_por_progreso[id_progreso] = "no_iniciado"
            porcentaje_por_progreso[id_progreso] = 0.0
            secuencia.append(id_progreso)

        secuencia_por_inscripcion[id_inscripcion] = secuencia
        indice_activo[id_inscripcion] = 0
        pool_activo.append(id_inscripcion)

    if cohortes_nuevas:
        cur.executemany(
            "INSERT INTO COHORTE (id_cohorte, nombre, fecha_inicio, fecha_fin, cupo_maximo) VALUES (?,?,?,?,?)",
            cohortes_nuevas,
        )

    if nuevas_inscripciones:
        cur.executemany(
            "INSERT INTO INSCRIPCION (id_inscripcion, id_estudiante, id_curso, id_cohorte, "
            "fecha_inscripcion, estado_curso, porcentaje_avance_curso) VALUES (?,?,?,?,?,?,?)",
            nuevas_inscripciones,
        )
        cur.executemany(
            "INSERT INTO PROGRESO_MODULO (id_progreso_modulo, id_inscripcion, id_modulo, "
            "estado_modulo, porcentaje_avance_modulo, fecha_actualizacion) VALUES (?,?,?,?,?,?)",
            nuevos_progresos_iniciales,
        )

    siguiente_id_evento = (cur.execute("SELECT MAX(id_evento) FROM EVENTO_PROGRESO").fetchone()[0] or 0) + 1

    eventos, actualizaciones = [], []
    for _ in range(eventos_por_dia):
        if not pool_activo:
            break  # todas las inscripciones ya completaron su curso o se estancaron

        id_inscripcion = random.choice(pool_activo)
        secuencia = secuencia_por_inscripcion[id_inscripcion]
        idx = indice_activo[id_inscripcion]
        id_progreso = secuencia[idx]

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

        # Avanzar (o congelar) el puntero de secuencia de esta inscripcion
        if nuevo_estado == "completado":
            idx += 1
            indice_activo[id_inscripcion] = idx
            if idx >= len(secuencia):
                pool_activo.remove(id_inscripcion)  # curso terminado (todos los modulos completados)
        elif nuevo_estado == "abandonado":
            pool_activo.remove(id_inscripcion)  # se estanco justo en este modulo, queda congelado

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
    print(
        f"Dia {fecha_a_cargar.isoformat()}: {len(eventos)} eventos cargados, "
        f"{len(nuevas_inscripciones)} inscripciones nuevas, "
        f"{len(nuevos_estudiantes)} estudiantes nuevos, "
        f"{len(cohortes_nuevas)} cohortes nuevas, "
        f"{len(cursos_nuevos)} cursos nuevos (sin borrar datos previos)."
    )


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
    SQL (etl_integracion.sql), no este export.

    Cada corrida se guarda en su PROPIA carpeta con fecha y hora exacta
    (ej: csv_export/2026-09-15_17-59-03/), para que NINGUNA exportacion
    se pierda ni se sobreescriba, aunque corras el comando varias veces
    en el mismo dia (o en el mismo minuto)."""
    if not tiene_datos(conn):
        print("No hay datos todavia. Corre primero: python generar_datos.py inicializar")
        return

    marca_tiempo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_fecha = CSV_DIR / marca_tiempo
    carpeta_fecha.mkdir(parents=True, exist_ok=True)

    conn.row_factory = sqlite3.Row
    for tabla in TABLAS_EXPORTAR:
        filas = conn.execute(f"SELECT * FROM {tabla}").fetchall()
        contenido_filas = []
        if filas:
            encabezado = list(filas[0].keys())
            contenido_filas = [tuple(f) for f in filas]
        else:
            encabezado = [d[0] for d in conn.execute(f"SELECT * FROM {tabla} LIMIT 0").description]

        ruta = carpeta_fecha / f"{tabla}.csv"
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(encabezado)
            writer.writerows(contenido_filas)

        print(f"  {tabla}: {len(filas)} filas -> {tabla}.csv")

    print(f"\nCSVs de esta corrida guardados en: {carpeta_fecha}")
    print("Ahora corre etl_integracion.sql contra tu MySQL para integrarlos.")


# ============================================================
# COMANDO: resincronizar-eventos
# ============================================================
def resincronizar_eventos(conn: sqlite3.Connection, offset: int) -> None:
    """Arregla el caso en que EVENTO_PROGRESO se vacio en la base LOCAL
    (por ejemplo, si se borraron filas a mano tratando de "destrabar" la
    simulacion) y sus id_evento volvieron a empezar desde 1. El problema:
    esos ids chocan con los que ya subiste antes a MySQL, y como
    etl_integracion.sql usa INSERT IGNORE con id_evento como llave, MySQL
    los ve como "ya los tengo" y no sube nada nuevo -> por eso parece que
    "no sube los datos".

    Esto le suma 'offset' a TODOS los id_evento de tu tabla local, para que
    ya no choquen con los que MySQL ya tiene. Se corre UNA sola vez.
    offset = el id_evento mas alto que ya exista en tu MySQL (correlo alla:
    SELECT MAX(id_evento) FROM EVENTO_PROGRESO;).
    """
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM EVENTO_PROGRESO").fetchone()[0]
    if total == 0:
        print("EVENTO_PROGRESO esta vacia localmente. No hay nada que resincronizar.")
        return

    minimo = cur.execute("SELECT MIN(id_evento) FROM EVENTO_PROGRESO").fetchone()[0]
    if minimo > offset:
        print(
            f"Los id_evento locales ya empiezan en {minimo}, que es mayor al offset "
            f"({offset}) que diste. No se hizo ningun cambio porque ya no colisionarian."
        )
        return

    cur.execute("UPDATE EVENTO_PROGRESO SET id_evento = id_evento + ?", (offset,))
    conn.commit()
    nuevo_max = cur.execute("SELECT MAX(id_evento) FROM EVENTO_PROGRESO").fetchone()[0]
    print(f"Listo: se le sumo {offset} a los {total} id_evento locales.")
    print(f"Ahora van de {minimo + offset} a {nuevo_max} (ya no chocan con lo que subiste antes).")
    print("Corre 'exportar-csv' de nuevo y luego etl_integracion.sql para subir estos eventos.")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Generador de datos local - Plataforma educativa")
    parser.add_argument(
        "accion",
        choices=["inicializar", "cargar-dia", "exportar-csv", "resincronizar-eventos"],
    )
    parser.add_argument("--eventos-por-dia", type=int, default=EVENTOS_POR_DIA_DEFAULT)
    parser.add_argument("--fecha", type=str, default=None, help="Forzar una fecha especifica (YYYY-MM-DD)")
    parser.add_argument(
        "--offset", type=int, default=None,
        help="Solo para resincronizar-eventos: el id_evento mas alto que ya tengas en MySQL",
    )
    args = parser.parse_args()

    conn = conectar()
    if args.accion == "inicializar":
        inicializar(conn)
    elif args.accion == "cargar-dia":
        cargar_dia(conn, args.eventos_por_dia, args.fecha)
    elif args.accion == "exportar-csv":
        exportar_csv(conn)
    elif args.accion == "resincronizar-eventos":
        if args.offset is None:
            print("Falta --offset. Usa: python generar_datos.py resincronizar-eventos --offset <numero>")
            print("Ese numero es el id_evento mas alto que ya tengas en MySQL (SELECT MAX(id_evento) FROM EVENTO_PROGRESO;).")
        else:
            resincronizar_eventos(conn, args.offset)
    conn.close()


if __name__ == "__main__":
    main()
