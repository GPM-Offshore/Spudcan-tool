
import streamlit as st
import matplotlib.pyplot as plt
from model import Geometry, GeometryType, Loads, SoilLayer, SoilClass, SoilType, solve_curve

st.set_page_config(page_title="Spudcan Penetration Tool", layout="wide")
st.title("Spudcan Penetration Tool v1.1")

with st.sidebar:
    st.header("Geometry")
    geometry_type = st.selectbox("Geometry type", [g.value for g in GeometryType], index=0)
    diameter_m = st.number_input("Effective diameter D (m)", min_value=0.1, value=15.3, step=0.1)
    max_area_m2 = st.number_input("Maximum area Amax (m^2)", min_value=0.1, value=184.6, step=0.1)
    tip_or_skirt_depth_m = st.number_input("Tip / skirt depth h (m)", min_value=0.1, value=1.4, step=0.1)

    st.header("Loads")
    stillwater_MN = st.number_input("Stillwater load (MN)", min_value=0.0, value=43.0, step=0.1)
    preload_MN = st.number_input("Preload load (MN)", min_value=0.0, value=77.7, step=0.1)

    st.header("Soil mechanism")
    soil_class = st.selectbox("Soil class", [s.value for s in SoilClass], index=0)

st.subheader("Soil inputs")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Top / single layer**")
    top_type = st.selectbox("Top layer type", [s.value for s in SoilType], key="toptype")
    top_bottom = st.number_input("Top layer bottom depth (m)", min_value=0.1, value=6.0, step=0.1)
    top_gamma = st.number_input("Top layer gamma (kN/m^3)", min_value=0.1, value=9.5, step=0.1)
    top_phi = st.number_input("Top layer phi (deg) if sand", min_value=0.0, value=32.5, step=0.5)
    top_su0 = st.number_input("Top layer su0 (kPa) if clay", min_value=0.0, value=100.0, step=1.0)
    top_k = st.number_input("Top layer k (kPa/m) if clay", min_value=0.0, value=5.0, step=1.0)

with col2:
    st.markdown("**Lower layer (only for layered cases)**")
    low_type = st.selectbox("Lower layer type", [s.value for s in SoilType], key="lowtype")
    low_gamma = st.number_input("Lower layer gamma (kN/m^3)", min_value=0.1, value=9.5, step=0.1)
    low_phi = st.number_input("Lower layer phi (deg) if sand", min_value=0.0, value=30.0, step=0.5)
    low_su0 = st.number_input("Lower layer su0 (kPa) if clay", min_value=0.0, value=90.0, step=1.0)
    low_k = st.number_input("Lower layer k (kPa/m) if clay", min_value=0.0, value=10.0, step=1.0)

if st.button("Run penetration model", type="primary"):
    geom = Geometry(geometry_type=GeometryType(geometry_type), diameter_m=diameter_m, max_area_m2=max_area_m2, tip_or_skirt_depth_m=tip_or_skirt_depth_m)
    loads = Loads(stillwater_MN=stillwater_MN, preload_MN=preload_MN)

    layers = [SoilLayer(top_m=0.0, bottom_m=top_bottom, soil_type=SoilType(top_type), gamma_eff_kN_m3=top_gamma, phi_deg=top_phi if top_type == "sand" else None, su0_kPa=top_su0 if top_type == "clay" else None, k_kPa_per_m=top_k if top_type == "clay" else 0.0)]

    if soil_class in ("sand_over_clay", "clay_over_sand"):
        layers.append(SoilLayer(top_m=top_bottom, bottom_m=50.0, soil_type=SoilType(low_type), gamma_eff_kN_m3=low_gamma, phi_deg=low_phi if low_type == "sand" else None, su0_kPa=low_su0 if low_type == "clay" else None, k_kPa_per_m=low_k if low_type == "clay" else 0.0))

    result = solve_curve(geom, loads, SoilClass(soil_class), layers)

    c1, c2, c3 = st.columns(3)
    c1.metric("Stillwater penetration (m)", "-" if result["z_stillwater"] is None else f"{result['z_stillwater']:.2f}")
    c2.metric("Preload penetration (m)", "-" if result["z_preload"] is None else f"{result['z_preload']:.2f}")
    c3.metric("Mechanism", result["mechanism"])

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(result["q_array"], result["z_array"], color="black", linewidth=1.2)
    ax.axvline(stillwater_MN, color="black", linestyle=":", linewidth=1.0, label="Stillwater")
    ax.axvline(preload_MN, color="black", linestyle="--", linewidth=1.0, label="Preload")
    if result["z_stillwater"] is not None:
        ax.scatter([stillwater_MN], [result["z_stillwater"]], color="black", s=20)
    if result["z_preload"] is not None:
        ax.scatter([preload_MN], [result["z_preload"]], color="black", s=20)

    x_max = max(preload_MN, stillwater_MN) * 1.3
    y_base = result["z_preload"] if result["z_preload"] is not None else max(result["z_array"])
    y_max = max(1.0, y_base * 1.6)

    ax.set_xlim(0, x_max)
    ax.set_ylim(0, y_max)
    ax.set_xlabel("Load / penetration resistance (MN)")
    ax.set_ylabel("Penetration depth (m)")
    ax.set_title("Load-penetration curve")
    ax.grid(True)
    ax.legend()
    st.pyplot(fig)
    st.caption("Reference: tip for conical / conical tip, skirt bottom for skirted.")
