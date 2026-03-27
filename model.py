
from dataclasses import dataclass
from enum import Enum
import math
import numpy as np

class GeometryType(str, Enum):
    CONICAL = "conical"
    CONICAL_TIP = "conical_tip"
    SKIRTED = "skirted"
    MODIFIED = "modified"

class SoilClass(str, Enum):
    SAND = "sand"
    CLAY = "clay"
    SAND_OVER_CLAY = "sand_over_clay"
    CLAY_OVER_SAND = "clay_over_sand"

class SoilType(str, Enum):
    SAND = "sand"
    CLAY = "clay"

@dataclass
class SoilLayer:
    top_m: float
    bottom_m: float
    soil_type: SoilType
    gamma_eff_kN_m3: float = 9.5
    phi_deg: float = None
    su0_kPa: float = None
    k_kPa_per_m: float = 0.0

    @property
    def thickness_m(self):
        return self.bottom_m - self.top_m

@dataclass
class Geometry:
    geometry_type: GeometryType
    diameter_m: float
    max_area_m2: float
    tip_or_skirt_depth_m: float

@dataclass
class Loads:
    stillwater_MN: float
    preload_MN: float

def nq(phi_deg):
    phi = math.radians(phi_deg)
    return math.exp(math.pi * math.tan(phi)) * math.tan(math.pi/4 + phi/2)**2

def area_mobilised(z_m, geom, exponent=3.0):
    h = max(geom.tip_or_skirt_depth_m, 0.1)
    ratio = min(max(z_m / h, 0.0), 1.0)
    return geom.max_area_m2 * ratio**exponent

def ks(z_m, D, a_s=0.05):
    if z_m <= 0:
        return 0.0
    z_star = z_m / D
    return z_star / (z_star + a_s)

def kc(z_m, D, alpha_c=3.0):
    return 1.0 + alpha_c * (z_m / D)

def su_at_depth(z_m, layer):
    su0 = layer.su0_kPa if layer.su0_kPa is not None else 100.0
    local_z = max(z_m - layer.top_m, 0.0)
    return su0 + layer.k_kPa_per_m * local_z

def base_sand(z_m, geom, layer):
    phi = layer.phi_deg if layer.phi_deg is not None else 30.0
    return area_mobilised(z_m, geom) * layer.gamma_eff_kN_m3 * geom.diameter_m * nq(phi) * ks(z_m, geom.diameter_m) / 1000.0

def base_clay(z_m, geom, layer, nc=6.0):
    return area_mobilised(z_m, geom) * nc * su_at_depth(z_m, layer) * kc(z_m, geom.diameter_m) / 1000.0

def skirt_resistance(z_m, geom, layer, alpha_s=0.22, delta_frac=0.08):
    if geom.geometry_type not in (GeometryType.SKIRTED, GeometryType.MODIFIED):
        return 0.0
    perimeter = math.pi * geom.diameter_m
    embed = min(max(z_m, 0.0), max(geom.tip_or_skirt_depth_m, 0.1))
    if layer.soil_type == SoilType.CLAY:
        tau = alpha_s * su_at_depth(z_m, layer)
    else:
        phi = layer.phi_deg if layer.phi_deg is not None else 30.0
        tau = delta_frac * layer.gamma_eff_kN_m3 * max(z_m, 0.5) * math.tan(math.radians(phi))
    return perimeter * embed * tau / 1000.0

def hanna_meyerhof_branch(z_m, geom, top_layer, lower_layer, beta=0.45):
    if lower_layer.soil_type == SoilType.CLAY:
        q_lower = base_clay(z_m, geom, lower_layer)
    else:
        q_lower = base_sand(z_m, geom, lower_layer)
    H = top_layer.thickness_m
    phi = top_layer.phi_deg if top_layer.phi_deg is not None else 30.0
    perimeter = math.pi * geom.diameter_m
    punch_side = perimeter * H * top_layer.gamma_eff_kN_m3 * math.tan(math.radians(phi)) * beta / 1000.0
    return q_lower + punch_side

def layered_response(z_m, geom, top_layer, lower_layer):
    q_upper = base_sand(z_m, geom, top_layer) if top_layer.soil_type == SoilType.SAND else base_clay(z_m, geom, top_layer)
    q_hm = hanna_meyerhof_branch(z_m, geom, top_layer, lower_layer)
    q_lower = base_sand(z_m, geom, lower_layer) if lower_layer.soil_type == SoilType.SAND else base_clay(z_m, geom, lower_layer)
    q = max(q_upper, q_hm, q_lower)
    mechanism = "upper-layer"
    if q == q_hm:
        mechanism = "Hanna-Meyerhof punching"
    elif q == q_lower:
        mechanism = "lower-layer recovery"
    q += skirt_resistance(z_m, geom, lower_layer)
    return q, mechanism

def total_resistance(z_m, geom, soil_class, layers):
    if soil_class == SoilClass.SAND:
        return base_sand(z_m, geom, layers[0]), "sand"
    if soil_class == SoilClass.CLAY:
        return base_clay(z_m, geom, layers[0]) + skirt_resistance(z_m, geom, layers[0]), "clay"
    return layered_response(z_m, geom, layers[0], layers[1])

def solve_curve(geom, loads, soil_class, layers, z_max_m=12.0, dz_m=0.005):
    z_vals, q_vals = [], []
    z_sw = None
    z_pl = None
    mechanism = "unknown"
    z = 0.0
    while z <= z_max_m + 1e-12:
        q, mechanism = total_resistance(z, geom, soil_class, layers)
        z_vals.append(z)
        q_vals.append(q)
        if z_sw is None and q >= loads.stillwater_MN:
            z_sw = z
        if z_pl is None and q >= loads.preload_MN:
            z_pl = z
            break
        z += dz_m
    return {"z_array": np.array(z_vals), "q_array": np.array(q_vals), "z_stillwater": z_sw, "z_preload": z_pl, "mechanism": mechanism}
