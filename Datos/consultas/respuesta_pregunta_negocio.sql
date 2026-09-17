-- ============================================================
-- RESPUESTA A LA PREGUNTA DE NEGOCIO:
-- "La plataforma no cuenta con un modelo de datos que conecte la
-- estructura de cursos y modulos con el progreso real de los
-- estudiantes, lo que impide identificar en que modulo especifico
-- se estancan o abandonan, comparar avance entre cohortes."
-- ============================================================
-- Estas dos consultas usan las tablas ya cargadas por
-- etl_integracion.sql (con la logica secuencial corregida en
-- generar_datos.py) para contestar directamente cada parte.
-- ============================================================

USE plataforma_educativa;

-- ------------------------------------------------------------
-- 1) EN QUE MODULO ESPECIFICO SE ESTANCAN O ABANDONAN
--    Cuenta, por curso y por modulo (en su orden real), cuantas
--    inscripciones quedaron congeladas ahi (estado_modulo =
--    'abandonado'). El modulo con el numero mas alto es el
--    "cuello de botella" de ese curso.
-- ------------------------------------------------------------
SELECT
    c.nombre                          AS curso,
    m.orden                           AS modulo_orden,
    m.nombre                          AS modulo,
    COUNT(*)                          AS estudiantes_estancados,
    ROUND(
        100.0 * COUNT(*) / (
            SELECT COUNT(*) FROM PROGRESO_MODULO pm2
            JOIN MODULO m2 ON m2.id_modulo = pm2.id_modulo
            WHERE m2.id_curso = c.id_curso AND m2.orden = m.orden
        ), 1
    )                                  AS pct_de_los_que_llegaron_al_modulo
FROM PROGRESO_MODULO pm
JOIN MODULO m ON m.id_modulo = pm.id_modulo
JOIN CURSO c  ON c.id_curso = m.id_curso
WHERE pm.estado_modulo = 'abandonado'
GROUP BY c.id_curso, c.nombre, m.orden, m.nombre
ORDER BY c.nombre, estudiantes_estancados DESC;

-- ------------------------------------------------------------
-- 2) COMPARAR AVANCE ENTRE COHORTES
--    Avance promedio y distribucion de estados por cohorte.
-- ------------------------------------------------------------
SELECT
    co.nombre                         AS cohorte,
    co.fecha_inicio,
    co.cupo_maximo,
    COUNT(DISTINCT i.id_inscripcion)  AS inscripciones,
    ROUND(
        100.0 * COUNT(DISTINCT i.id_inscripcion) / NULLIF(co.cupo_maximo, 0), 1
    )                                  AS pct_ocupacion_cupo,
    ROUND(AVG(i.porcentaje_avance_curso), 2) AS avance_promedio_pct,
    SUM(CASE WHEN i.estado_curso = 'completado' THEN 1 ELSE 0 END) AS completados,
    SUM(CASE WHEN i.estado_curso = 'en_curso'   THEN 1 ELSE 0 END) AS en_curso,
    SUM(CASE WHEN i.estado_curso = 'abandonado' THEN 1 ELSE 0 END) AS abandonados,
    ROUND(
        100.0 * SUM(CASE WHEN i.estado_curso = 'abandonado' THEN 1 ELSE 0 END)
        / COUNT(DISTINCT i.id_inscripcion), 1
    )                                  AS pct_abandono
FROM INSCRIPCION i
JOIN COHORTE co ON co.id_cohorte = i.id_cohorte
GROUP BY co.id_cohorte, co.nombre, co.fecha_inicio, co.cupo_maximo
ORDER BY co.fecha_inicio;
