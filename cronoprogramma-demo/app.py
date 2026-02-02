import streamlit as st
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

# =====================================================
# CONFIGURAZIONE GENERALE
# =====================================================
st.set_page_config(
    page_title="Cronoprogramma di Spesa",
    layout="wide"
)

NUM_FASI = 5  # ⚠️ FISSO: fasi sempre 1..5

CRONOPROGRAMMI = {
    "LINEARE":   {1: 7,  2: 13, 3: 20, 4: 27, 5: 33},
    "ANTICIPATO":{1: 10, 2: 45, 3: 22, 4: 13, 5: 10},
    "RITARDATO": {1: 10, 2: 13, 3: 22, 4: 45, 5: 10},
    "COSTANTE":  {1: 12, 2: 22, 3: 22, 4: 22, 5: 22},
    "CENTRATO":  {1: 8,  2: 20, 3: 44, 4: 20, 5: 8},
}

# =====================================================
# UTILS
# =====================================================
def euro(val):
    """Formato valuta € italiano"""
    return f"€ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =====================================================
# LOGICA CORE
# =====================================================
def build_plan(mese_avvio, mese_chiusura, costo_totale, tipo):
    durata = mese_chiusura - mese_avvio + 1

    if durata < NUM_FASI:
        raise ValueError("La durata dell'Activity deve essere almeno di 5 mesi")

    ampiezza_fase = durata / NUM_FASI

    # -------------------------------
    # 1️⃣ Assegnazione mese → fase
    # -------------------------------
    mesi = []
    mesi_per_fase = {f: 0 for f in range(1, NUM_FASI + 1)}

    for m in range(1, durata + 1):
        fase = int((m - 1) // ampiezza_fase) + 1
        fase = min(fase, NUM_FASI)

        mesi.append({
            "Mese": f"{mese_avvio + m - 1:02d}",
            "Mese progressivo": m,
            "Fase": fase
        })

        mesi_per_fase[fase] += 1

    # -------------------------------
    # 2️⃣ Costo per fase
    # -------------------------------
    costo_totale = Decimal(str(costo_totale)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    costo_per_fase = {}
    accumulato = Decimal("0.00")

    for f in range(1, NUM_FASI + 1):
        pct = Decimal(str(CRONOPROGRAMMI[tipo][f]))

        if f < NUM_FASI:
            val = (costo_totale * pct / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            accumulato += val
        else:
            val = costo_totale - accumulato  # aggiustamento finale

        costo_per_fase[f] = val

    # -------------------------------
    # 3️⃣ Distribuzione mensile uniforme
    # -------------------------------
    for f in range(1, NUM_FASI + 1):
        lista = [m for m in mesi if m["Fase"] == f]
        count = len(lista)

        base = (costo_per_fase[f] / count).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        somma = Decimal("0.00")

        for i, m in enumerate(lista):
            m["% Fase"] = CRONOPROGRAMMI[tipo][f]
            m["% Fase per mese"] = round(CRONOPROGRAMMI[tipo][f] / count, 2)

            if i < count - 1:
                m["Costo atteso mensile (€)"] = float(base)
                somma += base
            else:
                m["Costo atteso mensile (€)"] = float(
                    (costo_per_fase[f] - somma).quantize(Decimal("0.01"))
                )

    df_mesi = pd.DataFrame(mesi)

    # -------------------------------
    # 4️⃣ Riepilogo per fase
    # -------------------------------
    riepilogo = []
    for f in range(1, NUM_FASI + 1):
        mesi_fase = mesi_per_fase[f]
        pct_fase = CRONOPROGRAMMI[tipo][f]

        riepilogo.append({
            "Fase": f,
            "Conteggio mesi per fase": mesi_fase,
            "% Fase": pct_fase,
            "% Fase per mese": round(pct_fase / mesi_fase, 2),
            "Costo totale fase (€)": float(costo_per_fase[f])
        })

    df_fasi = pd.DataFrame(riepilogo)

    return df_mesi, df_fasi, durata, costo_totale


# =====================================================
# EXCEL EXPORT
# =====================================================
def build_excel(df_mesi, df_fasi):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_mesi.to_excel(writer, sheet_name="Dettaglio_mensile", index=False)
        df_fasi.to_excel(writer, sheet_name="Riepilogo_fasi", index=False)
    output.seek(0)
    return output


# =====================================================
# UI
# =====================================================
st.title("📊 Cronoprogramma di Spesa")

with st.sidebar:
    st.header("Parametri Activity")

    mese_avvio = st.number_input("Mese di avvio", min_value=1, value=2)
    mese_chiusura = st.number_input("Mese di chiusura", min_value=1, value=14)
    costo_totale = st.number_input("Costo totale (€)", min_value=0.0, value=10000.0, step=500.0)
    tipo = st.selectbox("Tipo cronoprogramma", list(CRONOPROGRAMMI.keys()))

try:
    df_mesi, df_fasi, durata, costo_tot = build_plan(
        mese_avvio, mese_chiusura, costo_totale, tipo
    )
except Exception as e:
    st.error(str(e))
    st.stop()

# -------------------------------
# KPI
# -------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Durata Activity", f"{durata} mesi")
c2.metric("Costo totale", euro(costo_tot))
c3.metric("Cronoprogramma", tipo)

# -------------------------------
# TABELLA MENSILE (NO INDICE)
# -------------------------------
st.subheader("📅 Dettaglio mensile")

df_mesi_fmt = df_mesi.copy().reset_index(drop=True)
df_mesi_fmt["Costo atteso mensile (€)"] = df_mesi_fmt[
    "Costo atteso mensile (€)"
].apply(euro)

st.dataframe(df_mesi_fmt, use_container_width=True)

# -------------------------------
# TABELLA RIEPILOGO FASI (NO INDICE)
# -------------------------------
st.subheader("📦 Riepilogo per fase")

df_fasi_fmt = df_fasi.copy().reset_index(drop=True)
df_fasi_fmt["Costo totale fase (€)"] = df_fasi_fmt[
    "Costo totale fase (€)"
].apply(euro)

st.dataframe(df_fasi_fmt, use_container_width=True)

# -------------------------------
# DOWNLOAD EXCEL
# -------------------------------
st.subheader("⬇️ Esporta risultati")

excel_file = build_excel(df_mesi, df_fasi)

st.download_button(
    label="📥 Scarica Excel cronoprogramma",
    data=excel_file,
    file_name="cronoprogramma_spesa.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# -------------------------------
# GRAFICI
# -------------------------------
st.subheader("📈 Distribuzione dei costi")

col1, col2 = st.columns(2)

with col1:
    st.write("Costo per fase")
    st.bar_chart(
        df_fasi.set_index("Fase")["Costo totale fase (€)"]
    )

with col2:
    st.write("Costo mensile")
    st.line_chart(
        df_mesi.set_index("Mese progressivo")["Costo atteso mensile (€)"]
    )
