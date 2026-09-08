-- ============================================================
-- ESQUEMA MYSQL (base de datos DESTINO) - Plataforma Educativa
-- ============================================================
-- Esta es la base a donde vamos a migrar (ETL) los datos que
-- genera tu script de Python (generar_datos.py) desde SQLite.
--
-- Los IDs se insertan explicitamente durante el ETL (vienen del
-- SQLite de origen), por eso NO se usa AUTO_INCREMENT en las PK.
-- ============================================================

CREATE DATABASE IF NOT EXISTS plataforma_educativa
    CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE plataforma_educativa;

DROP TABLE IF EXISTS EVENTO_PROGRESO;
DROP TABLE IF EXISTS PROGRESO_MODULO;
DROP TABLE IF EXISTS INSCRIPCION;
DROP TABLE IF EXISTS MODULO;
DROP TABLE IF EXISTS CURSO;
DROP TABLE IF EXISTS COHORTE;
DROP TABLE IF EXISTS ESTUDIANTE;
DROP TABLE IF EXISTS etl_log;

-- ================= DIMENSIONES =================

CREATE TABLE ESTUDIANTE (
    id_estudiante   INT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    apellido        VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    fecha_registro  DATE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE COHORTE (
    id_cohorte    INT PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    fecha_inicio  DATE NOT NULL,
    fecha_fin     DATE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE CURSO (
    id_curso        INT PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    descripcion     VARCHAR(500),
    categoria       VARCHAR(100),
    fecha_creacion  DATE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE MODULO (
    id_modulo        INT PRIMARY KEY,
    id_curso         INT NOT NULL,
    nombre           VARCHAR(150) NOT NULL,
    orden            INT NOT NULL,
    descripcion      VARCHAR(500),
    duracion_horas   INT,
    CONSTRAINT fk_modulo_curso FOREIGN KEY (id_curso) REFERENCES CURSO(id_curso)
) ENGINE=InnoDB;

-- ================= TABLAS DE HECHO =================

CREATE TABLE INSCRIPCION (
    id_inscripcion            INT PRIMARY KEY,
    id_estudiante             INT NOT NULL,
    id_curso                  INT NOT NULL,
    id_cohorte                INT NOT NULL,
    fecha_inscripcion         DATE NOT NULL,
    estado_curso              VARCHAR(20) NOT NULL,
    porcentaje_avance_curso   DECIMAL(5,2) DEFAULT 0,
    CONSTRAINT fk_inscripcion_estudiante FOREIGN KEY (id_estudiante) REFERENCES ESTUDIANTE(id_estudiante),
    CONSTRAINT fk_inscripcion_curso FOREIGN KEY (id_curso) REFERENCES CURSO(id_curso),
    CONSTRAINT fk_inscripcion_cohorte FOREIGN KEY (id_cohorte) REFERENCES COHORTE(id_cohorte)
) ENGINE=InnoDB;

CREATE TABLE PROGRESO_MODULO (
    id_progreso_modulo        INT PRIMARY KEY,
    id_inscripcion            INT NOT NULL,
    id_modulo                 INT NOT NULL,
    estado_modulo             VARCHAR(20) NOT NULL,
    porcentaje_avance_modulo  DECIMAL(5,2) DEFAULT 0,
    fecha_actualizacion       DATE,
    CONSTRAINT fk_progreso_inscripcion FOREIGN KEY (id_inscripcion) REFERENCES INSCRIPCION(id_inscripcion),
    CONSTRAINT fk_progreso_modulo FOREIGN KEY (id_modulo) REFERENCES MODULO(id_modulo)
) ENGINE=InnoDB;

CREATE TABLE EVENTO_PROGRESO (
    id_evento            INT PRIMARY KEY,
    id_progreso_modulo   INT NOT NULL,
    tipo_evento          VARCHAR(30) NOT NULL,
    fecha_evento         DATE NOT NULL,
    detalle              VARCHAR(255),
    CONSTRAINT fk_evento_progreso FOREIGN KEY (id_progreso_modulo) REFERENCES PROGRESO_MODULO(id_progreso_modulo)
) ENGINE=InnoDB;

-- ================= CONTROL DEL ETL =================
-- Registra cada corrida del ETL que trae datos desde el SQLite
-- de origen hacia este MySQL (auditoria / evita cargas duplicadas)

CREATE TABLE etl_log (
    id_carga            INT AUTO_INCREMENT PRIMARY KEY,
    fecha_dato_cargado  DATE NOT NULL UNIQUE,
    fecha_ejecucion_etl DATETIME NOT NULL,
    filas_evento        INT NOT NULL
) ENGINE=InnoDB;




