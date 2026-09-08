-- ============================================================
-- REINICIAR MYSQL (vaciar todo para empezar de nuevo desde hoy)
-- ============================================================
-- Corre esto UNA VEZ antes de volver a generar datos desde cero.
-- Deja las tablas vacias pero no las borra (no hace falta volver
-- a correr schema_mysql.sql despues de esto).
-- ============================================================

USE plataforma_educativa;

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE EVENTO_PROGRESO;
TRUNCATE PROGRESO_MODULO;
TRUNCATE INSCRIPCION;
TRUNCATE MODULO;
TRUNCATE CURSO;
TRUNCATE COHORTE;
TRUNCATE ESTUDIANTE;
TRUNCATE etl_log;

TRUNCATE stg_estudiante;
TRUNCATE stg_cohorte;
TRUNCATE stg_curso;
TRUNCATE stg_modulo;
TRUNCATE stg_inscripcion;
TRUNCATE stg_progreso_modulo;
TRUNCATE stg_evento_progreso;

SET FOREIGN_KEY_CHECKS = 1;

-- Verificacion: todo debe salir en 0
SELECT 'ESTUDIANTE' AS tabla, COUNT(*) AS filas FROM ESTUDIANTE
UNION ALL SELECT 'COHORTE', COUNT(*) FROM COHORTE
UNION ALL SELECT 'CURSO', COUNT(*) FROM CURSO
UNION ALL SELECT 'MODULO', COUNT(*) FROM MODULO
UNION ALL SELECT 'INSCRIPCION', COUNT(*) FROM INSCRIPCION
UNION ALL SELECT 'PROGRESO_MODULO', COUNT(*) FROM PROGRESO_MODULO
UNION ALL SELECT 'EVENTO_PROGRESO', COUNT(*) FROM EVENTO_PROGRESO
UNION ALL SELECT 'etl_log', COUNT(*) FROM etl_log;