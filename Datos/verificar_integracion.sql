-- ============================================================
-- VERIFICACION: ¿la integracion a MySQL quedo bien?
-- ============================================================
-- Corre esto en Workbench (contra tu base plataforma_educativa)
-- cada vez que quieras confirmar que los datos llegaron completos
-- y sin romper ninguna relacion.
-- ============================================================

USE plataforma_educativa;

-- ------------------------------------------------------------
-- 1) CONTEO POR TABLA
--    Compara estos numeros con los que te imprimio
--    "python generar_datos.py exportar-csv" en tu terminal.
--    Deben ser EXACTAMENTE iguales.
-- ------------------------------------------------------------
SELECT 'ESTUDIANTE' AS tabla, COUNT(*) AS filas FROM ESTUDIANTE
UNION ALL SELECT 'COHORTE', COUNT(*) FROM COHORTE
UNION ALL SELECT 'CURSO', COUNT(*) FROM CURSO
UNION ALL SELECT 'MODULO', COUNT(*) FROM MODULO
UNION ALL SELECT 'INSCRIPCION', COUNT(*) FROM INSCRIPCION
UNION ALL SELECT 'PROGRESO_MODULO', COUNT(*) FROM PROGRESO_MODULO
UNION ALL SELECT 'EVENTO_PROGRESO', COUNT(*) FROM EVENTO_PROGRESO
UNION ALL SELECT 'etl_log', COUNT(*) FROM etl_log;

-- ------------------------------------------------------------
-- 2) INTEGRIDAD REFERENCIAL (deben salir todos en 0)
--    Si algun numero aqui es mayor a 0, hay una fila que quedo
--    "huerfana" (apunta a un id que no existe en la otra tabla).
-- ------------------------------------------------------------
SELECT 'MODULO sin CURSO valido' AS chequeo, COUNT(*) AS problemas
FROM MODULO m LEFT JOIN CURSO c ON c.id_curso = m.id_curso
WHERE c.id_curso IS NULL

UNION ALL
SELECT 'INSCRIPCION sin ESTUDIANTE valido', COUNT(*)
FROM INSCRIPCION i LEFT JOIN ESTUDIANTE e ON e.id_estudiante = i.id_estudiante
WHERE e.id_estudiante IS NULL

UNION ALL
SELECT 'INSCRIPCION sin CURSO valido', COUNT(*)
FROM INSCRIPCION i LEFT JOIN CURSO c ON c.id_curso = i.id_curso
WHERE c.id_curso IS NULL

UNION ALL
SELECT 'INSCRIPCION sin COHORTE valido', COUNT(*)
FROM INSCRIPCION i LEFT JOIN COHORTE co ON co.id_cohorte = i.id_cohorte
WHERE co.id_cohorte IS NULL

UNION ALL
SELECT 'PROGRESO_MODULO sin INSCRIPCION valida', COUNT(*)
FROM PROGRESO_MODULO pm LEFT JOIN INSCRIPCION i ON i.id_inscripcion = pm.id_inscripcion
WHERE i.id_inscripcion IS NULL

UNION ALL
SELECT 'PROGRESO_MODULO sin MODULO valido', COUNT(*)
FROM PROGRESO_MODULO pm LEFT JOIN MODULO m ON m.id_modulo = pm.id_modulo
WHERE m.id_modulo IS NULL

UNION ALL
SELECT 'EVENTO_PROGRESO sin PROGRESO_MODULO valido', COUNT(*)
FROM EVENTO_PROGRESO ev LEFT JOIN PROGRESO_MODULO pm ON pm.id_progreso_modulo = ev.id_progreso_modulo
WHERE pm.id_progreso_modulo IS NULL;

-- ------------------------------------------------------------
-- 3) PKs DUPLICADAS (deben salir todos en 0)
--    Si algo sale mayor a 0, un mismo ID se guardo mas de una vez
--    (no deberia pasar porque es PRIMARY KEY, pero sirve para
--    detectar si por error se crearon tablas con nombre distinto).
-- ------------------------------------------------------------
SELECT 'ESTUDIANTE' AS tabla, COUNT(*) - COUNT(DISTINCT id_estudiante) AS duplicados FROM ESTUDIANTE
UNION ALL SELECT 'COHORTE', COUNT(*) - COUNT(DISTINCT id_cohorte) FROM COHORTE
UNION ALL SELECT 'CURSO', COUNT(*) - COUNT(DISTINCT id_curso) FROM CURSO
UNION ALL SELECT 'MODULO', COUNT(*) - COUNT(DISTINCT id_modulo) FROM MODULO
UNION ALL SELECT 'INSCRIPCION', COUNT(*) - COUNT(DISTINCT id_inscripcion) FROM INSCRIPCION
UNION ALL SELECT 'PROGRESO_MODULO', COUNT(*) - COUNT(DISTINCT id_progreso_modulo) FROM PROGRESO_MODULO
UNION ALL SELECT 'EVENTO_PROGRESO', COUNT(*) - COUNT(DISTINCT id_evento) FROM EVENTO_PROGRESO;

-- ------------------------------------------------------------
-- 4) COHERENCIA DE NEGOCIO (deben salir todos en 0)
-- ------------------------------------------------------------
-- 4a) Todo estudiante inscrito debe tener progreso en cada modulo de su curso
SELECT 'Inscripciones sin ningun progreso de modulo' AS chequeo, COUNT(*) AS problemas
FROM INSCRIPCION i
WHERE NOT EXISTS (SELECT 1 FROM PROGRESO_MODULO pm WHERE pm.id_inscripcion = i.id_inscripcion)

UNION ALL
-- 4b) porcentaje_avance_curso fuera de rango 0-100
SELECT 'Porcentajes de curso fuera de 0-100', COUNT(*)
FROM INSCRIPCION
WHERE porcentaje_avance_curso < 0 OR porcentaje_avance_curso > 100

UNION ALL
-- 4c) eventos con fecha anterior a la inscripcion (inconsistente)
SELECT 'Eventos con fecha anterior a su inscripcion', COUNT(*)
FROM EVENTO_PROGRESO ev
JOIN PROGRESO_MODULO pm ON pm.id_progreso_modulo = ev.id_progreso_modulo
JOIN INSCRIPCION i ON i.id_inscripcion = pm.id_inscripcion
WHERE ev.fecha_evento < i.fecha_inscripcion;
