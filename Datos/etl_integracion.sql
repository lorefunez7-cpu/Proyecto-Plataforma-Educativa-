-- ============================================================
-- ETL DE INTEGRACION (100% SQL, corre dentro de MySQL)
-- ============================================================
-- Flujo completo:
--   1) python generar_datos.py cargar-dia      (SQLite: agrega el dia)
--   2) python generar_datos.py exportar-csv    (SQLite -> CSV, sin
--                                               logica de negocio)
--   3) COPIA los 7 CSV generados hacia la carpeta que te indica:
--        SHOW VARIABLES LIKE 'secure_file_priv';
--      (en tu caso: C:\ProgramData\MySQL\MySQL Server 8.0\Uploads\)
--   4) corre este script completo en Workbench
--
-- Por que se copian los CSV a esa carpeta y no se leen directo de
-- tu OneDrive: LOAD DATA LOCAL INFILE (leer desde tu PC/cliente) esta
-- bloqueado por Workbench recientes por seguridad. La alternativa
-- soportada es LOAD DATA INFILE (sin LOCAL): el propio servidor MySQL
-- lee el archivo, pero SOLO desde la carpeta que el admin autorizo
-- (secure_file_priv). Por eso hay que copiar los CSV ahi.
--
-- Que hace el script:
--   - carga los CSV (ya copiados) a tablas staging (stg_*)
--   - dimensiones: INSERT IGNORE (si ya existe, se ignora)
--   - INSCRIPCION / PROGRESO_MODULO: INSERT ... ON DUPLICATE
--     KEY UPDATE (upsert: si ya existe, actualiza su estado)
--   - EVENTO_PROGRESO: INSERT IGNORE por PK (id_evento), asi
--     nunca se duplica un evento aunque re-exportes todo
--   - registra la corrida en etl_log
-- ============================================================

USE plataforma_educativa;

-- ------------------------------------------------------------
-- 0) TABLAS STAGING (aterrizaje temporal de cada CSV)
--    mismo shape que las tablas finales, sin llaves foraneas,
--    para que LOAD DATA no falle por orden ni por FK
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_estudiante (
    id_estudiante   INT,
    nombre          VARCHAR(100),
    apellido        VARCHAR(100),
    email           VARCHAR(150),
    fecha_registro  DATE
);

CREATE TABLE IF NOT EXISTS stg_cohorte (
    id_cohorte    INT,
    nombre        VARCHAR(100),
    fecha_inicio  DATE,
    fecha_fin     DATE
);

CREATE TABLE IF NOT EXISTS stg_curso (
    id_curso        INT,
    nombre          VARCHAR(150),
    descripcion     VARCHAR(500),
    categoria       VARCHAR(100),
    fecha_creacion  DATE
);

CREATE TABLE IF NOT EXISTS stg_modulo (
    id_modulo        INT,
    id_curso         INT,
    nombre           VARCHAR(150),
    orden            INT,
    descripcion      VARCHAR(500),
    duracion_horas   INT
);

CREATE TABLE IF NOT EXISTS stg_inscripcion (
    id_inscripcion            INT,
    id_estudiante             INT,
    id_curso                  INT,
    id_cohorte                INT,
    fecha_inscripcion         DATE,
    estado_curso              VARCHAR(20),
    porcentaje_avance_curso   DECIMAL(5,2)
);

CREATE TABLE IF NOT EXISTS stg_progreso_modulo (
    id_progreso_modulo        INT,
    id_inscripcion            INT,
    id_modulo                 INT,
    estado_modulo             VARCHAR(20),
    porcentaje_avance_modulo  DECIMAL(5,2),
    fecha_actualizacion       DATE
);

CREATE TABLE IF NOT EXISTS stg_evento_progreso (
    id_evento            INT,
    id_progreso_modulo   INT,
    tipo_evento          VARCHAR(30),
    fecha_evento         DATE,
    detalle              VARCHAR(255)
);

-- limpiar staging de la corrida anterior
TRUNCATE stg_estudiante;
TRUNCATE stg_cohorte;
TRUNCATE stg_curso;
TRUNCATE stg_modulo;
TRUNCATE stg_inscripcion;
TRUNCATE stg_progreso_modulo;
TRUNCATE stg_evento_progreso;

-- ------------------------------------------------------------
-- 1) EXTRACT: cargar cada CSV (ya copiado a la carpeta Uploads
--    del servidor) a su tabla staging
-- ------------------------------------------------------------
LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/ESTUDIANTE.csv'
INTO TABLE stg_estudiante
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/COHORTE.csv'
INTO TABLE stg_cohorte
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/CURSO.csv'
INTO TABLE stg_curso
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/MODULO.csv'
INTO TABLE stg_modulo
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/INSCRIPCION.csv'
INTO TABLE stg_inscripcion
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/PROGRESO_MODULO.csv'
INTO TABLE stg_progreso_modulo
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/EVENTO_PROGRESO.csv'
INTO TABLE stg_evento_progreso
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

-- ------------------------------------------------------------
-- 2) TRANSFORM + LOAD: integrar staging -> tablas finales
--    (todo en SQL: INSERT IGNORE para dimensiones y eventos,
--     ON DUPLICATE KEY UPDATE para las tablas que cambian de estado)
-- ------------------------------------------------------------

-- Dimensiones: casi nunca cambian, se insertan solo si son nuevas
INSERT IGNORE INTO ESTUDIANTE (id_estudiante, nombre, apellido, email, fecha_registro)
SELECT id_estudiante, nombre, apellido, email, fecha_registro FROM stg_estudiante;

INSERT IGNORE INTO COHORTE (id_cohorte, nombre, fecha_inicio, fecha_fin)
SELECT id_cohorte, nombre, fecha_inicio, fecha_fin FROM stg_cohorte;

INSERT IGNORE INTO CURSO (id_curso, nombre, descripcion, categoria, fecha_creacion)
SELECT id_curso, nombre, descripcion, categoria, fecha_creacion FROM stg_curso;

INSERT IGNORE INTO MODULO (id_modulo, id_curso, nombre, orden, descripcion, duracion_horas)
SELECT id_modulo, id_curso, nombre, orden, descripcion, duracion_horas FROM stg_modulo;

-- INSCRIPCION: upsert (el % de avance y el estado cambian cada dia)
INSERT INTO INSCRIPCION (id_inscripcion, id_estudiante, id_curso, id_cohorte,
                          fecha_inscripcion, estado_curso, porcentaje_avance_curso)
SELECT id_inscripcion, id_estudiante, id_curso, id_cohorte,
       fecha_inscripcion, estado_curso, porcentaje_avance_curso
FROM stg_inscripcion AS s
ON DUPLICATE KEY UPDATE
    estado_curso = s.estado_curso,
    porcentaje_avance_curso = s.porcentaje_avance_curso;

-- PROGRESO_MODULO: upsert (estado_modulo y % avanzan dia a dia)
INSERT INTO PROGRESO_MODULO (id_progreso_modulo, id_inscripcion, id_modulo,
                              estado_modulo, porcentaje_avance_modulo, fecha_actualizacion)
SELECT id_progreso_modulo, id_inscripcion, id_modulo,
       estado_modulo, porcentaje_avance_modulo, fecha_actualizacion
FROM stg_progreso_modulo AS s
ON DUPLICATE KEY UPDATE
    estado_modulo = s.estado_modulo,
    porcentaje_avance_modulo = s.porcentaje_avance_modulo,
    fecha_actualizacion = s.fecha_actualizacion;

-- EVENTO_PROGRESO: solo se insertan, nunca cambian.
-- INSERT IGNORE por PK evita duplicar eventos ya cargados en corridas
-- anteriores, aunque el CSV traiga el historico completo cada vez.
INSERT IGNORE INTO EVENTO_PROGRESO (id_evento, id_progreso_modulo, tipo_evento, fecha_evento, detalle)
SELECT id_evento, id_progreso_modulo, tipo_evento, fecha_evento, detalle
FROM stg_evento_progreso;

-- ------------------------------------------------------------
-- 3) AUDITORIA: registrar esta corrida del ETL
--    (cuenta cuantos eventos NUEVOS trajo el staging que no
--    estaban antes en etl_log, y el ultimo dia cargado).
--    HAVING COUNT(*) > 0 evita insertar una fila NULL cuando el
--    staging viene vacio (por ejemplo si aun no corriste cargar-dia).
-- ------------------------------------------------------------
INSERT INTO etl_log (fecha_dato_cargado, fecha_ejecucion_etl, filas_evento)
SELECT
    MAX(s.fecha_evento),
    NOW(),
    COUNT(*)
FROM stg_evento_progreso s
WHERE NOT EXISTS (
    SELECT 1 FROM etl_log l WHERE l.fecha_dato_cargado = s.fecha_evento
)
HAVING COUNT(*) > 0
ON DUPLICATE KEY UPDATE
    fecha_ejecucion_etl = VALUES(fecha_ejecucion_etl),
    filas_evento = VALUES(filas_evento);

-- ------------------------------------------------------------
-- 4) VERIFICACION RAPIDA
-- ------------------------------------------------------------
SELECT 'ESTUDIANTE' AS tabla, COUNT(*) AS filas FROM ESTUDIANTE
UNION ALL SELECT 'COHORTE', COUNT(*) FROM COHORTE
UNION ALL SELECT 'CURSO', COUNT(*) FROM CURSO
UNION ALL SELECT 'MODULO', COUNT(*) FROM MODULO
UNION ALL SELECT 'INSCRIPCION', COUNT(*) FROM INSCRIPCION
UNION ALL SELECT 'PROGRESO_MODULO', COUNT(*) FROM PROGRESO_MODULO
UNION ALL SELECT 'EVENTO_PROGRESO', COUNT(*) FROM EVENTO_PROGRESO
UNION ALL SELECT 'etl_log', COUNT(*) FROM etl_log;