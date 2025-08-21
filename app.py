# app.py
# — App de Streamlit para:
# 1) Subir Archivo A (CSV/Excel), elegir la columna objetivo.
# 2) Subir Archivo B (CSV/Excel) con una columna que contiene números a excluir.
# 3) Generar resultado = Archivo A sin las filas cuyo valor en la columna elegida
#    aparece en Archivo B. Además, crea una hoja "numeros_repetidos" con el listado
#    de los números detectados, más sus conteos en A y en B.
# 4) Descarga en Excel con dos hojas: "resultado" y "numeros_repetidos" y, opcionalmente, CSV.

import streamlit as st
import pandas as pd
from io import BytesIO
import csv
import re

st.set_page_config(page_title="Filtrar CSV por lista", page_icon="🧹", layout="wide")
st.title("🧹Limpiador de Duplicados")
st.caption(
    "Sube tu Archivo A, elige la columna a limpiar, luego sube el Archivo B con los números a eliminar. "
    "El resultado excluye esas filas y genera una hoja con los números detectados como repetidos."
)

# --------------------------- Utilidades --------------------------- #

def _ensure_bytes(uploaded_file):
    """Lee el archivo subido como bytes para poder reusarlo múltiples veces."""
    if uploaded_file is None:
        return None
    return uploaded_file.getvalue()  # Streamlit UploadedFile soporta getvalue()


def _sniff_delimiter(sample_bytes):
    """Intenta adivinar el delimitador más común entre , ; \t |."""
    if not sample_bytes:
        return None
    text = sample_bytes.decode("utf-8", errors="ignore")
    try:
        dialect = csv.Sniffer().sniff(text, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        return None


def _read_table(file_bytes, file_name, sep_mode="auto", custom_sep=",", header_mode="infer"):
    """Lee CSV o Excel desde bytes con heurísticas de separador y codificación.

    sep_mode: "auto", "coma", "punto_y_coma", "tab", "pipe", "otro"
    header_mode: "infer" o "sin encabezados"
    """
    if file_bytes is None:
        return None, "No hay datos"

    name_lower = (file_name or "").lower()
    header = 0 if header_mode == "infer" else None

    # Lectura de Excel
    if name_lower.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(BytesIO(file_bytes), header=header)
            return df, None
        except Exception as e:
            return None, f"Error leyendo Excel: {e}"

    # CSV/TXT
    sep = None
    if sep_mode == "auto":
        # Primer intento: pandas con sep None (inferencia)
        try:
            df = pd.read_csv(BytesIO(file_bytes), sep=None, engine="python", header=header)
            return df, None
        except Exception:
            # Segundo intento: usar csv.Sniffer()
            sniffed = _sniff_delimiter(file_bytes[:10000])
            if sniffed:
                try:
                    df = pd.read_csv(BytesIO(file_bytes), sep=sniffed, engine="python", header=header)
                    return df, None
                except Exception as e2:
                    return None, f"No se pudo leer el CSV (separador '{sniffed}'): {e2}"
            return None, "No se pudo inferir el delimitador automáticamente. Selecciónalo manualmente."
    else:
        m = {
            "coma": ",",
            "punto_y_coma": ";",
            "tab": "\t",
            "pipe": "|",
            "otro": custom_sep or ",",
        }
        sep = m.get(sep_mode, ",")
        try:
            df = pd.read_csv(BytesIO(file_bytes), sep=sep, engine="python", header=header)
            return df, None
        except Exception as e:
            return None, f"Error leyendo CSV con separador '{sep}': {e}"


def _normalize_series(s, digits_only=False, strip_spaces=True):
    """Convierte a string, recorta espacios y opcionalmente conserva solo dígitos.
    Útil para comparar números tipo teléfono / ID.
    """
    s = s.astype(str)
    if strip_spaces:
        s = s.str.strip()
    if digits_only:
        s = s.apply(lambda x: re.sub(r"\D", "", x))
    return s


# --------------------------- Paso 1: Archivo A --------------------------- #

st.header("1) Sube el Archivo A")
colA1, colA2, colA3 = st.columns([2, 1.1, 1])
with colA1:
    file_a = st.file_uploader("Archivo A (CSV, TXT o Excel)", type=["csv", "txt", "xlsx", "xls"], key="file_a")

with colA2:
    sep_a_mode = st.selectbox(
        "Separador (A)",
        ["auto", "coma", "punto_y_coma", "tab", "pipe", "otro"],
        index=0,
        help="Si falla la lectura automática, elige el separador manualmente."
    )

with colA3:
    header_a = st.selectbox("Encabezados (A)", ["infer", "sin encabezados"], index=0)

custom_sep_a = None
if sep_a_mode == "otro":
    custom_sep_a = st.text_input("Especifica el separador para A", value=",")

file_a_bytes = _ensure_bytes(file_a)

df_a, err_a = (None, None)
if file_a_bytes:
    df_a, err_a = _read_table(file_a_bytes, getattr(file_a, "name", None), sep_mode=sep_a_mode, custom_sep=custom_sep_a, header_mode=header_a)

if err_a:
    st.error(err_a)

if df_a is not None:
    st.success(f"Archivo A cargado: {df_a.shape[0]} filas × {df_a.shape[1]} columnas")
    st.dataframe(df_a.head(50), use_container_width=True)

    # Selección de columna objetivo en A
    st.subheader("Columna objetivo en Archivo A")
    col_a_target = st.selectbox("¿Qué columna de A quieres usar para comparar/eliminar?", df_a.columns)
else:
    col_a_target = None

# --------------------------- Paso 2: Archivo B --------------------------- #

st.header("2) Sube el Archivo B (contiene los números a eliminar)")
colB1, colB2, colB3 = st.columns([2, 1.1, 1])
with colB1:
    file_b = st.file_uploader("Archivo B (CSV, TXT o Excel) – una columna con los números", type=["csv", "txt", "xlsx", "xls"], key="file_b")
with colB2:
    sep_b_mode = st.selectbox(
        "Separador (B)", ["auto", "coma", "punto_y_coma", "tab", "pipe", "otro"], index=0
    )
with colB3:
    header_b = st.selectbox("Encabezados (B)", ["infer", "sin encabezados"], index=0)

custom_sep_b = None
if sep_b_mode == "otro":
    custom_sep_b = st.text_input("Especifica el separador para B", value=",")

file_b_bytes = _ensure_bytes(file_b)

df_b, err_b = (None, None)
if file_b_bytes:
    df_b, err_b = _read_table(file_b_bytes, getattr(file_b, "name", None), sep_mode=sep_b_mode, custom_sep=custom_sep_b, header_mode=header_b)

if err_b:
    st.error(err_b)

col_norm1, col_norm2 = st.columns([1, 3])
with col_norm1:
    digits_only = st.checkbox("Normalizar: conservar solo dígitos", value=False, help="Útil si hay guiones, espacios u otros símbolos en los números.")

# Si B no tiene encabezados, pandas crea columnas 0,1,2... Permitimos elegir la columna cierta.
col_b_source = None
if df_b is not None:
    st.success(f"Archivo B cargado: {df_b.shape[0]} filas × {df_b.shape[1]} columnas")
    st.dataframe(df_b.head(50), use_container_width=True)
    col_b_source = st.selectbox("¿Qué columna de B contiene los números?", df_b.columns)

# --------------------------- Paso 3: Procesar --------------------------- #

st.header("3) Procesar y descargar")
if st.button("🧮 Ejecutar limpieza", type="primary", use_container_width=False):
    if df_a is None or df_b is None:
        st.error("Debes cargar ambos archivos A y B.")
    elif col_a_target is None or col_b_source is None:
        st.error("Debes seleccionar la columna objetivo en A y la columna de números en B.")
    else:
        # Preparar series comparables
        a_series = _normalize_series(df_a[col_a_target], digits_only=digits_only)
        b_series = _normalize_series(df_b[col_b_source].dropna(), digits_only=digits_only)

        # Conjunto de valores en B
        b_set = set(b_series.tolist())

        # Filas de A cuyo valor aparece en B
        mask_repetidos = a_series.isin(b_set)
        filas_repetidas = mask_repetidos.sum()

        # DataFrames resultado
        df_resultado = df_a.loc[~mask_repetidos].copy()

        # Hoja "numeros_repetidos" con métricas
        #  - numero
        #  - conteo_en_A (cuántas filas de A tenían ese número)
        #  - conteo_en_B (por si B tiene duplicados)
        rep_en_a = (
            a_series[mask_repetidos]
            .to_frame(name="numero")
            .groupby("numero", as_index=True)
            .size()
            .rename("conteo_en_A")
        )
        rep_en_b = (
            b_series
            .to_frame(name="numero")
            .groupby("numero", as_index=True)
            .size()
            .rename("conteo_en_B")
        )
        numeros_repetidos = (
            pd.DataFrame(index=sorted(set(a_series[mask_repetidos].unique())))
            .merge(rep_en_a, left_index=True, right_index=True, how="left")
            .merge(rep_en_b, left_index=True, right_index=True, how="left")
            .reset_index()
            .rename(columns={"index": "numero"})
        )

        # Resumen
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("Filas en A (total)", f"{len(df_a):,}")
        col_r2.metric("Filas eliminadas (coinciden con B)", f"{filas_repetidas:,}")
        col_r3.metric("Filas finales", f"{len(df_resultado):,}")

        st.subheader("Vista previa del resultado (primeras 100 filas)")
        st.dataframe(df_resultado.head(100), use_container_width=True)

        st.subheader("Vista previa – hoja 'numeros_repetidos'")
        st.dataframe(numeros_repetidos, use_container_width=True)

        # Exportar a Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_resultado.to_excel(writer, index=False, sheet_name="resultado")
            numeros_repetidos.to_excel(writer, index=False, sheet_name="numeros_repetidos")
        output.seek(0)

        st.download_button(
            label="📥 Descargar Excel (resultado + numeros_repetidos)",
            data=output,
            file_name="resultado_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # También CSV solo del resultado, si lo prefieren
        csv_result = df_resultado.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 Descargar solo resultado (CSV)",
            data=csv_result,
            file_name="resultado_filtrado.csv",
            mime="text/csv",
        )

st.divider()
st.markdown(
    "**Notas:**\n"
    "- Si ves errores del tipo *'No columns to parse from file'* o *'Could not determine delimiter'*, usa el selector de separador manual o carga el archivo como Excel.\n"
    "- La opción *Normalizar: conservar solo dígitos* ayuda si tus números tienen guiones, espacios o paréntesis.\n"
    "- Si tu Archivo B trae más de una columna, asegúrate de elegir la que contiene los números a eliminar.\n"
)

