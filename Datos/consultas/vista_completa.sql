-- ============================================================
-- VISTA COMPLETA: todas las columnas relevantes en una sola tabla
-- ============================================================
-- Une ESTUDIANTE + COHORTE + CURSO + MODULO + INSCRIPCION +
-- PROGRESO_MODULO en un solo resultado (una fila por cada
-- estudiante-modulo). No incluye EVENTO_PROGRESO aqui porque esa
-- tabla tiene MUCHAS filas por cada progreso (multiplicaria el
-- resultado); si la necesitas, hay una segunda consulta abajo.
-- ============================================================

USE plataforma_educativa;

SELECT
    e.id_estudiante,
    e.nombre,
    e.apellido,
    e.email,
    e.fecha_registro,

    co.id_cohorte,
    co.nombre        AS cohorte,
    co.fecha_inicio   AS cohorte_inicio,
    co.fecha_fin      AS cohorte_fin,
    co.cupo_maximo    AS cohorte_cupo_maximo,

    c.id_curso,
    c.nombre         AS curso,
    c.categoria,
    c.fecha_creacion AS curso_creado,

    i.id_inscripcion,
    i.fecha_inscripcion,
    i.estado_curso,
    i.porcentaje_avance_curso,

    m.id_modulo,
    m.nombre         AS modulo,
    m.orden          AS modulo_orden,
    m.duracion_horas,

    pm.id_progreso_modulo,
    pm.estado_modulo,
    pm.porcentaje_avance_modulo,
    pm.fecha_actualizacion

FROM ESTUDIANTE e
JOIN INSCRIPCION i        ON i.id_estudiante = e.id_estudiante
JOIN COHORTE co           ON co.id_cohorte = i.id_cohorte
JOIN CURSO c              ON c.id_curso = i.id_curso
JOIN PROGRESO_MODULO pm   ON pm.id_inscripcion = i.id_inscripcion
JOIN MODULO m             ON m.id_modulo = pm.id_modulo
ORDER BY e.id_estudiante, i.id_inscripcion, m.orden;

-- ------------------------------------------------------------
-- OPCIONAL: la misma vista pero agregando tambien los eventos
-- (cuidado: esto crea muchas mas filas, una por cada evento)
-- ------------------------------------------------------------
-- SELECT
--     e.nombre, e.apellido, c.nombre AS curso, m.nombre AS modulo,
--     pm.estado_modulo, pm.porcentaje_avance_modulo,
--     ev.tipo_evento, ev.fecha_evento, ev.detalle
-- FROM ESTUDIANTE e
-- JOIN INSCRIPCION i        ON i.id_estudiante = e.id_estudiante
-- JOIN CURSO c              ON c.id_curso = i.id_curso
-- JOIN PROGRESO_MODULO pm   ON pm.id_inscripcion = i.id_inscripcion
-- JOIN MODULO m             ON m.id_modulo = pm.id_modulo
-- JOIN EVENTO_PROGRESO ev   ON ev.id_progreso_modulo = pm.id_progreso_modulo
-- ORDER BY e.id_estudiante, ev.fecha_evento;
