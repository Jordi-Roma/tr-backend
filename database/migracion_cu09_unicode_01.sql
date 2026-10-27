-- CU09: identidad de nombres Unicode, independiente de LC_CTYPE/LC_COLLATE.
-- init_db.py ejecuta y registra esta migración dentro de una sola transacción.
-- ICU root mantiene las tildes y evita reglas regionales como la I turca.
CREATE COLLATION public.stylear_catalogo_unicode (
    provider = icu,
    locale = 'und',
    deterministic = true
);

CREATE FUNCTION public.normalizar_nombre_catalogo(valor text)
RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path = pg_catalog
AS $$
    SELECT normalize(
        lower(normalize(btrim(valor), NFC) COLLATE public.stylear_catalogo_unicode),
        NFC
    )
$$;

-- Mantener la misma fotografía para el diagnóstico y la creación de índices.
-- Las consultas continúan; las escrituras esperan hasta finalizar la migración.
LOCK TABLE public.categoria, public.talla, public.color, public.marca,
    public.temporada, public.coleccion IN SHARE ROW EXCLUSIVE MODE;

-- No borrar, fusionar ni renombrar registros heredados automáticamente.
-- Una colisión revierte TODO, incluidos función y collation recién creados.
DO $$
DECLARE
    identidad RECORD;
    duplicados jsonb;
BEGIN
    FOR identidad IN SELECT * FROM (VALUES
        ('categoria', ''),
        ('talla', ', tipo_prenda'),
        ('color', ''),
        ('marca', ''),
        ('temporada', ', anio'),
        ('coleccion', ', temporada_id')
    ) AS identidades(tabla, campos) LOOP
        EXECUTE format(
            'SELECT jsonb_agg(d) FROM (
                SELECT empresa_id,
                    public.normalizar_nombre_catalogo(nombre) COLLATE "C" AS nombre_normalizado
                    %s, array_agg(id ORDER BY id) AS ids
                FROM public.%I
                GROUP BY empresa_id,
                    public.normalizar_nombre_catalogo(nombre) COLLATE "C" %s
                HAVING count(*) > 1
                ORDER BY empresa_id, min(id)
                LIMIT 20
            ) d', identidad.campos, identidad.tabla, identidad.campos
        ) INTO duplicados;
        IF duplicados IS NOT NULL THEN
            RAISE EXCEPTION 'CU09 Unicode: existen nombres duplicados en %.', identidad.tabla
                USING ERRCODE = '23505',
                DETAIL = jsonb_build_object('tabla', identidad.tabla, 'grupos', duplicados)::text,
                HINT = 'Revisar los IDs indicados antes de reintentar init_db.py. No se modificó ningún registro.';
        END IF;
    END LOOP;
END $$;

DROP INDEX public.uq_categoria_empresa_nombre;
CREATE UNIQUE INDEX uq_categoria_empresa_nombre ON public.categoria
    (empresa_id, (public.normalizar_nombre_catalogo(nombre) COLLATE "C"));

DROP INDEX public.uq_talla_empresa_nombre_tipo;
CREATE UNIQUE INDEX uq_talla_empresa_nombre_tipo ON public.talla
    (empresa_id, (public.normalizar_nombre_catalogo(nombre) COLLATE "C"), tipo_prenda);

DROP INDEX public.uq_color_empresa_nombre;
CREATE UNIQUE INDEX uq_color_empresa_nombre ON public.color
    (empresa_id, (public.normalizar_nombre_catalogo(nombre) COLLATE "C"));

DROP INDEX public.uq_marca_empresa_nombre;
CREATE UNIQUE INDEX uq_marca_empresa_nombre ON public.marca
    (empresa_id, (public.normalizar_nombre_catalogo(nombre) COLLATE "C"));

DROP INDEX public.uq_temporada_empresa_nombre_anio;
CREATE UNIQUE INDEX uq_temporada_empresa_nombre_anio ON public.temporada
    (empresa_id, (public.normalizar_nombre_catalogo(nombre) COLLATE "C"), anio);

-- Colección conserva la identidad empresa + temporada + nombre; también se
-- protege frente a dos INSERT directos que no pasen por el controlador.
CREATE UNIQUE INDEX uq_coleccion_empresa_temporada_nombre ON public.coleccion
    (empresa_id, temporada_id, (public.normalizar_nombre_catalogo(nombre) COLLATE "C"));
