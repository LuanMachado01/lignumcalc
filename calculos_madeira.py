# -*- coding: utf-8 -*-
"""
Módulo para cálculo de propriedades de resistência, rigidez e verificações
de estruturas de madeira conforme NBR 7190-1:2022.

Versão Modificada:
- Coeficiente k_M é passado como argumento para funções relevantes
  (flexão oblíqua, flexotração, flexocompressão) em vez de usar default 0.7.
- Função verificar_flexocompressao_com_estabilidade retorna valores
  detalhados (11 no total) para esbeltez e ratio.
- calcular_f_t90d implementa o mínimo de (kmod*ft90k/gt) e (0.06*ft0d).
- Cálculo de f_c0d (Tab. 3) usa f_c0k.
- Cálculo de f_c90d usa o f_c0d correto no limite.
- verificar_compressao_perpendicular AINDA USA ÁREA TOTAL (A=b*h) - ATENÇÃO!

Suposições Mantidas:
- Propriedades das tabelas referenciadas a U=12%.
"""

import math
import traceback

# --------------------------------------------------------------------------
# Constantes (Coeficientes de Minoração - Item 5.8.5 NBR 7190-1:2022)
# --------------------------------------------------------------------------
GAMMA_C = 1.4  # Compressão paralela e perpendicular
GAMMA_T = 1.4  # Tração paralela e perpendicular
GAMMA_M = 1.4  # Flexão
GAMMA_V = 1.8  # Cisalhamento
TOL = 1e-9     # Tolerância geral para comparações com zero

# --------------------------------------------------------------------------
# Tabelas de Propriedades da Madeira (NBR 7190-1:2022, Tabelas 2 e 3)
# --------------------------------------------------------------------------
# (Mantém a definição das tabelas como no arquivo original)
tabelas_madeira = {
    "estrutural": {
        "C14": {"f_mk": 14, "f_t0k": 8, "f_t90k": 0.4, "f_c0k": 16, "f_c90k": 2.0, "f_vk": 3.0, "E_0med": 7000, "E_005": 4700, "E_90med": 200, "G_med": 400, "densidade_k": 290, "densidade_med": 350},
        "C16": {"f_mk": 16, "f_t0k": 10, "f_t90k": 0.4, "f_c0k": 17, "f_c90k": 2.2, "f_vk": 3.2, "E_0med": 8000, "E_005": 5400, "E_90med": 300, "G_med": 500, "densidade_k": 310, "densidade_med": 370},
        "C18": {"f_mk": 18, "f_t0k": 11, "f_t90k": 0.4, "f_c0k": 18, "f_c90k": 2.2, "f_vk": 3.4, "E_0med": 9000, "E_005": 6000, "E_90med": 300, "G_med": 600, "densidade_k": 320, "densidade_med": 380},
        "C20": {"f_mk": 20, "f_t0k": 12, "f_t90k": 0.4, "f_c0k": 19, "f_c90k": 2.3, "f_vk": 3.6, "E_0med": 9500, "E_005": 6400, "E_90med": 300, "G_med": 600, "densidade_k": 330, "densidade_med": 390},
        "C22": {"f_mk": 22, "f_t0k": 13, "f_t90k": 0.4, "f_c0k": 20, "f_c90k": 2.4, "f_vk": 3.8, "E_0med": 10000, "E_005": 6700, "E_90med": 300, "G_med": 600, "densidade_k": 340, "densidade_med": 410},
        "C24": {"f_mk": 24, "f_t0k": 14, "f_t90k": 0.4, "f_c0k": 21, "f_c90k": 2.5, "f_vk": 4.0, "E_0med": 11000, "E_005": 7400, "E_90med": 400, "G_med": 700, "densidade_k": 350, "densidade_med": 420},
        "C27": {"f_mk": 27, "f_t0k": 16, "f_t90k": 0.4, "f_c0k": 22, "f_c90k": 2.6, "f_vk": 4.0, "E_0med": 11500, "E_005": 7700, "E_90med": 400, "G_med": 700, "densidade_k": 370, "densidade_med": 450},
        "C30": {"f_mk": 30, "f_t0k": 18, "f_t90k": 0.4, "f_c0k": 23, "f_c90k": 2.7, "f_vk": 4.0, "E_0med": 12000, "E_005": 8000, "E_90med": 400, "G_med": 800, "densidade_k": 380, "densidade_med": 460},
        "C35": {"f_mk": 35, "f_t0k": 21, "f_t90k": 0.4, "f_c0k": 25, "f_c90k": 2.8, "f_vk": 4.0, "E_0med": 13000, "E_005": 8700, "E_90med": 400, "G_med": 800, "densidade_k": 400, "densidade_med": 480},
        "C40": {"f_mk": 40, "f_t0k": 24, "f_t90k": 0.4, "f_c0k": 26, "f_c90k": 2.9, "f_vk": 4.0, "E_0med": 14000, "E_005": 9400, "E_90med": 500, "G_med": 900, "densidade_k": 420, "densidade_med": 500},
        "C45": {"f_mk": 45, "f_t0k": 27, "f_t90k": 0.4, "f_c0k": 27, "f_c90k": 3.1, "f_vk": 4.0, "E_0med": 15000, "E_005": 10000, "E_90med": 500, "G_med": 900, "densidade_k": 440, "densidade_med": 520},
        "C50": {"f_mk": 50, "f_t0k": 30, "f_t90k": 0.4, "f_c0k": 29, "f_c90k": 3.2, "f_vk": 4.0, "E_0med": 16000, "E_005": 11000, "E_90med": 500, "G_med": 1000, "densidade_k": 460, "densidade_med": 550},
        "D18": {"f_mk": 18, "f_t0k": 11, "f_t90k": 0.6, "f_c0k": 18, "f_c90k": 7.5, "f_vk": 3.4, "E_0med": 9500, "E_005": 8000, "E_90med": 600, "G_med": 600, "densidade_k": 475, "densidade_med": 570},
        "D24": {"f_mk": 24, "f_t0k": 14, "f_t90k": 0.6, "f_c0k": 21, "f_c90k": 7.8, "f_vk": 4.0, "E_0med": 10000, "E_005": 8500, "E_90med": 700, "G_med": 600, "densidade_k": 485, "densidade_med": 580},
        "D30": {"f_mk": 30, "f_t0k": 18, "f_t90k": 0.6, "f_c0k": 23, "f_c90k": 8.0, "f_vk": 4.0, "E_0med": 11000, "E_005": 9200, "E_90med": 700, "G_med": 700, "densidade_k": 530, "densidade_med": 640},
        "D35": {"f_mk": 35, "f_t0k": 21, "f_t90k": 0.6, "f_c0k": 25, "f_c90k": 8.1, "f_vk": 4.0, "E_0med": 12000, "E_005": 10000, "E_90med": 800, "G_med": 800, "densidade_k": 540, "densidade_med": 650},
        "D40": {"f_mk": 40, "f_t0k": 24, "f_t90k": 0.6, "f_c0k": 26, "f_c90k": 8.3, "f_vk": 4.0, "E_0med": 13000, "E_005": 11000, "E_90med": 900, "G_med": 800, "densidade_k": 560, "densidade_med": 660},
        "D50": {"f_mk": 50, "f_t0k": 30, "f_t90k": 0.6, "f_c0k": 29, "f_c90k": 9.3, "f_vk": 4.0, "E_0med": 14000, "E_005": 12000, "E_90med": 900, "G_med": 900, "densidade_k": 620, "densidade_med": 750},
        "D60": {"f_mk": 60, "f_t0k": 36, "f_t90k": 0.6, "f_c0k": 32, "f_c90k": 11.0, "f_vk": 4.5, "E_0med": 17000, "E_005": 14000, "E_90med": 1100, "G_med": 1100, "densidade_k": 700, "densidade_med": 840},
        "D70": {"f_mk": 70, "f_t0k": 42, "f_t90k": 0.6, "f_c0k": 34, "f_c90k": 13.5, "f_vk": 5.0, "E_0med": 20000, "E_005": 16800, "E_90med": 1330, "G_med": 1250, "densidade_k": 900, "densidade_med": 1080}
    },
    "nativa": {
        "D20": {"f_c0k": 20, "f_v0k": 4, "E_c0med": 10000, "densidade_med": 500},
        "D30": {"f_c0k": 30, "f_v0k": 5, "E_c0med": 12000, "densidade_med": 625},
        "D40": {"f_c0k": 40, "f_v0k": 6, "E_c0med": 14500, "densidade_med": 750},
        "D50": {"f_c0k": 50, "f_v0k": 7, "E_c0med": 16500, "densidade_med": 850},
        "D60": {"f_c0k": 60, "f_v0k": 8, "E_c0med": 19500, "densidade_med": 1000}
    }
}
# (Mantém o preenchimento de derivados para tabela nativa)
for classe, props in tabelas_madeira["nativa"].items():
    e_c0med = props.get("E_c0med")
    if e_c0med:
        props["E_0med"] = e_c0med
        props["E_005"] = 0.7 * e_c0med if abs(e_c0med) > TOL else 0.0
        props["E_90med"] = e_c0med / 20 if abs(e_c0med) > TOL else 0.0
        props["G_med"] = e_c0med / 16 if abs(e_c0med) > TOL else 0.0
    fc0k = props.get("f_c0k")
    if fc0k:
        props["f_t0k"] = props.get("f_t0k", fc0k)
        props["f_mk"] = props.get("f_mk", fc0k)
        props["f_t90k"] = props.get("f_t90k", fc0k * 0.05)
        props["f_c90k"] = props.get("f_c90k", fc0k * 0.25)
    rho_med = props.get("densidade_med")
    if rho_med and abs(rho_med) > TOL:
        props["densidade_k"] = rho_med / 1.2
    props["f_vk"] = props.get("f_v0k")

kmod1_valores = {
    "permanente": 0.60, "longa": 0.70, "media": 0.80, "curta": 0.90, "instantanea": 1.10,
}
kmod2_valores = {
    "classe_1": 1.00, "classe_2": 0.90, "classe_3": 0.80, "classe_4": 0.70
}

# --------------------------------------------------------------------------
# Funções de Cálculo Kmod
# --------------------------------------------------------------------------
# (Mantém as funções calcular_kmod1, calcular_kmod2, calcular_kmod)
def calcular_kmod1(classe_carregamento, tipo_madeira="serrada"):
    """Calcula kmod1 baseado na classe de carregamento e tipo (Tabela 4)."""
    kmod1 = kmod1_valores.get(classe_carregamento)
    if kmod1 is None:
        raise ValueError(f"Classe de carregamento '{classe_carregamento}' inválida.")
    return kmod1

def calcular_kmod2(classe_umidade, tipo_madeira="serrada"):
    """Calcula kmod2 baseado na classe de umidade e tipo (Tabela 5)."""
    if tipo_madeira == "mlcc" and classe_umidade == "classe_4":
         raise ValueError("MLCC não é permitido para classe de umidade 4 (NBR 7190:2022 Tabela 5, nota a).")
    kmod2 = kmod2_valores.get(classe_umidade)
    if kmod2 is None:
        raise ValueError(f"Classe de umidade '{classe_umidade}' inválida.")
    return kmod2

def calcular_kmod(classe_carregamento, classe_umidade, tipo_madeira="serrada"):
    """Calcula o kmod total."""
    kmod1 = calcular_kmod1(classe_carregamento, tipo_madeira)
    kmod2 = calcular_kmod2(classe_umidade, tipo_madeira)
    return kmod1 * kmod2

# --------------------------------------------------------------------------
# Obter Propriedades da Madeira
# --------------------------------------------------------------------------
# (Mantém a função obter_propriedades_madeira)
def obter_propriedades_madeira(tipo_tabela, classe_madeira):
    """Busca as propriedades da madeira na tabela especificada."""
    tabela = tabelas_madeira.get(tipo_tabela)
    if not tabela:
        raise ValueError(f"Tipo de tabela '{tipo_tabela}' inválido. Use 'estrutural' ou 'nativa'.")
    propriedades = tabela.get(classe_madeira)
    if not propriedades:
        raise KeyError(f"Classe '{classe_madeira}' inválida ou não encontrada para tabela '{tipo_tabela}'.")
    chaves_essenciais = ["f_c0k", "f_vk", "E_0med", "E_005"]
    for chave in chaves_essenciais:
         if propriedades.get(chave) is None:
             raise KeyError(f"Propriedade essencial '{chave}' não encontrada para {tipo_tabela} {classe_madeira}. Verifique a definição das tabelas.")
    return propriedades

# --------------------------------------------------------------------------
# Calcular Resistências de Cálculo (f_d) - COM CORREÇÕES
# --------------------------------------------------------------------------
# (Mantém as funções calcular_f_t0d, calcular_f_t90d, calcular_f_c0d, calcular_f_c90d, calcular_f_vd, calcular_f_md)
def calcular_f_t0d(f_t0k, k_mod):
    """Calcula f_t0,d (Tração Paralela de Cálculo)."""
    if f_t0k is None: return 0.0
    if abs(k_mod) < TOL: return 0.0
    return k_mod * f_t0k / GAMMA_T

def calcular_f_t90d(f_t90k, f_t0d_calc, k_mod):
    """Calcula f_t90,d (Tração Perpendicular de Cálculo) conforme NBR 7190 Item 6.2.3."""
    if f_t90k is None: f_t90k = 0.0
    if abs(k_mod) < TOL: return 0.0
    if f_t0d_calc is None or f_t0d_calc < TOL:
         return (k_mod * f_t90k / GAMMA_T) if f_t90k > TOL else 0.0
    f_t90d_base = k_mod * f_t90k / GAMMA_T
    limite_006_ft0d = 0.06 * f_t0d_calc
    return min(f_t90d_base, limite_006_ft0d)

def calcular_f_c0d(f_c0k, k_mod):
    """Calcula f_c0,d (Compressão Paralela de Cálculo)."""
    if f_c0k is None or f_c0k <= TOL:
        raise ValueError("f_c0k não pode ser None ou não positivo para calcular f_c0d.")
    if abs(k_mod) < TOL: return 0.0
    return k_mod * f_c0k / GAMMA_C

def calcular_f_c90d(f_c90k, f_c0d_calc, alpha_n, k_mod):
    """Calcula f_c90,d (Compressão Perpendicular de Cálculo) com limite do Item 6.3.3."""
    if f_c90k is None: return 0.0
    if abs(k_mod) < TOL: return 0.0
    f_c90d_base = k_mod * f_c90k / GAMMA_C
    if f_c0d_calc is None or f_c0d_calc < TOL:
         return f_c90d_base
    limite_superior = 0.25 * f_c0d_calc * alpha_n
    return min(f_c90d_base, limite_superior)

def calcular_f_vd(f_vk, k_mod):
    """Calcula f_v,d (Cisalhamento de Cálculo)."""
    if f_vk is None or f_vk <= TOL:
        raise ValueError("f_vk (ou f_v0k) não pode ser None ou não positivo para calcular f_vd.")
    if abs(k_mod) < TOL: return 0.0
    return k_mod * f_vk / GAMMA_V

def calcular_f_md(f_mk, k_mod):
    """Calcula f_m,d (Flexão de Cálculo)."""
    if f_mk is None: return 0.0
    if abs(k_mod) < TOL: return 0.0
    return k_mod * f_mk / GAMMA_M

# --------------------------------------------------------------------------
# Obter Módulos de Elasticidade
# --------------------------------------------------------------------------
# (Mantém as funções obter_E0_med, obter_E0_05, obter_E0_ef)
def obter_E0_med(propriedades):
    """Obtém E_0,med (pode ser E_c0,med para nativas)."""
    e0_med = propriedades.get("E_0med")
    if e0_med is None: raise KeyError("E_0med não encontrado.")
    if e0_med <= TOL: raise ValueError("E_0med não pode ser zero ou negativo.")
    return e0_med

def obter_E0_05(propriedades):
    """Obtém E_0,05 (pode ser estimado como 0.7*E_c0,med para nativas)."""
    e0_05 = propriedades.get("E_005")
    if e0_05 is None: raise KeyError("E_005 não encontrado.")
    if e0_05 <= TOL: raise ValueError("E_005 não pode ser zero ou negativo.")
    return e0_05

def obter_E0_ef(propriedades, k_mod):
    """Calcula E_0,ef para estabilidade lateral."""
    e0_med = obter_E0_med(propriedades)
    if abs(k_mod) < TOL: return 0.0
    return k_mod * e0_med

# --------------------------------------------------------------------------
# Cálculos Geométricos
# --------------------------------------------------------------------------
# (Mantém a função calcular_propriedades_geometricas)
def calcular_propriedades_geometricas(largura_b, altura_h):
    """Calcula A, Ix, Iy, Wx, Wy, ix, iy para seção retangular."""
    if largura_b <= TOL or altura_h <= TOL:
        raise ValueError(f"Dimensões b ({largura_b}) e h ({altura_h}) devem ser positivas.")
    area = largura_b * altura_h
    ix = (largura_b * altura_h**3) / 12
    iy = (altura_h * largura_b**3) / 12
    wx = ix / (altura_h / 2) if abs(altura_h) > TOL else 0.0
    wy = iy / (largura_b / 2) if abs(largura_b) > TOL else 0.0
    raio_ix = math.sqrt(ix / area) if area > TOL else 0.0
    raio_iy = math.sqrt(iy / area) if area > TOL else 0.0
    return {"area": area, "I_x": ix, "I_y": iy, "W_x": wx, "W_y": wy, "i_x": raio_ix, "i_y": raio_iy}

# --------------------------------------------------------------------------
# Verificações ELU (Estado Limite Último)
# --------------------------------------------------------------------------

# (Mantém as funções verificar_tracao_simples, verificar_compressao_perpendicular,
#  verificar_cisalhamento, verificar_flexao_simples_reta)
def verificar_tracao_simples(N_sd_t, A, f_t0d):
    """Verifica ELU para tração simples paralela."""
    if A <= TOL: return False, abs(N_sd_t), 0.0
    if f_t0d <= TOL: return abs(N_sd_t) < TOL, abs(N_sd_t), 0.0
    NRd = f_t0d * A
    passou = abs(N_sd_t) <= NRd + TOL
    return passou, abs(N_sd_t), NRd

def verificar_compressao_perpendicular(N_sd_90, Area_usada, f_c90d):
     """Verifica ELU para compressão perpendicular às fibras (Usa Area_usada)."""
     if Area_usada <= TOL: return False, abs(N_sd_90), 0.0
     if f_c90d <= TOL: return abs(N_sd_90) < TOL, abs(N_sd_90), 0.0
     NRd = f_c90d * Area_usada
     passou = abs(N_sd_90) <= NRd + TOL
     return passou, abs(N_sd_90), NRd

def verificar_cisalhamento(V_sd, A, f_vd):
    """Verifica ELU para cisalhamento longitudinal em vigas retangulares."""
    if A <= TOL: return False, abs(V_sd), 0.0
    if f_vd <= TOL: return abs(V_sd) < TOL, abs(V_sd), 0.0
    VRd = (f_vd * A) / 1.5
    passou = abs(V_sd) <= VRd + TOL
    return passou, abs(V_sd), VRd

def verificar_flexao_simples_reta(M_sd, W, f_md):
    """Verifica ELU para flexão simples reta."""
    if W <= TOL: return False, abs(M_sd), 0.0
    if f_md <= TOL: return abs(M_sd) < TOL, abs(M_sd), 0.0
    MRd = f_md * W
    passou = abs(M_sd) <= MRd + TOL
    return passou, abs(M_sd), MRd

# --- VERIFICAÇÕES COMBINADAS MODIFICADAS ---

def verificar_flexao_obliqua(M_sdx, M_sdy, Wx, Wy, f_md, k_M): # <-- k_M como parâmetro
    """Verifica ELU para flexão oblíqua (Item 6.3.5), usando k_M fornecido."""
    if Wx <= TOL or Wy <= TOL: return False, float('inf')
    if f_md <= TOL:
        passou_sem_res = (abs(M_sdx) < TOL and abs(M_sdy) < TOL)
        return passou_sem_res, 0.0

    termo_x = abs(M_sdx) / (Wx * f_md) if abs(Wx * f_md) > TOL else float('inf')
    termo_y = abs(M_sdy) / (Wy * f_md) if abs(Wy * f_md) > TOL else float('inf')

    ratio1 = termo_x + k_M * termo_y
    ratio2 = k_M * termo_x + termo_y
    ratio_max = max(ratio1, ratio2)

    passou = ratio_max <= 1.0 + TOL
    return passou, ratio_max

def verificar_flexotracao(N_sd_t, M_sdx, M_sdy, A, Wx, Wy, f_t0d, f_md, k_M): # <-- k_M como parâmetro
    """Verifica ELU para flexotração (Item 6.3.6), usando k_M fornecido."""
    if A <= TOL or Wx <= TOL or Wy <= TOL: return False, float('inf')
    if f_t0d <= TOL or f_md <= TOL:
        passou_sem_res = (abs(N_sd_t) < TOL and abs(M_sdx) < TOL and abs(M_sdy) < TOL)
        return passou_sem_res, 0.0

    termo_N = abs(N_sd_t) / (A * f_t0d) if abs(A * f_t0d) > TOL else float('inf')
    termo_Mx = abs(M_sdx) / (Wx * f_md) if abs(Wx * f_md) > TOL else float('inf')
    termo_My = abs(M_sdy) / (Wy * f_md) if abs(Wy * f_md) > TOL else float('inf')

    ratio1 = termo_N + termo_Mx + k_M * termo_My
    ratio2 = termo_N + k_M * termo_Mx + termo_My
    ratio_max = max(ratio1, ratio2)

    passou = ratio_max <= 1.0 + TOL
    return passou, ratio_max

# --- Funções de Estabilidade (Item 6.5) ---

# (Mantém as funções calcular_indices_esbeltez, calcular_coeficiente_reducao_kc)
def calcular_indices_esbeltez(comprimento_L, Ke, raio_giracao_i, f_c0k, E_005):
    """Calcula índice de esbeltez (lambda) e esbeltez relativa (lambda_rel)."""
    if raio_giracao_i is None or raio_giracao_i <= TOL: raise ValueError(f"Raio de giração inválido ({raio_giracao_i}).")
    if E_005 is None or E_005 <= TOL: raise ValueError(f"E_005 inválido ({E_005}).")
    if f_c0k is None or f_c0k <= TOL: raise ValueError(f"f_c0k inválido ({f_c0k}).")
    if comprimento_L < 0 or Ke < 0: raise ValueError(f"Comprimento L ({comprimento_L}) ou Ke ({Ke}) não podem ser negativos.")

    L0 = Ke * comprimento_L
    if L0 < TOL: return 0.0, 0.0

    lambda_i = L0 / raio_giracao_i
    termo_raiz_lambda_rel = f_c0k / E_005
    if termo_raiz_lambda_rel < 0: raise ValueError(f"Termo f_c0k/E_005 ({termo_raiz_lambda_rel:.2e}) negativo.")

    lambda_rel_i = (lambda_i / math.pi) * math.sqrt(termo_raiz_lambda_rel)
    return lambda_i, lambda_rel_i

def calcular_coeficiente_reducao_kc(lambda_rel, beta_c=0.2):
    """Calcula o coeficiente de redução kc para estabilidade (Item 6.5.5)."""
    if lambda_rel is None or lambda_rel < 0: raise ValueError(f"lambda_rel inválido ({lambda_rel}).")
    if lambda_rel <= 0.3 + TOL: return 1.0

    k = 0.5 * (1 + beta_c * (lambda_rel - 0.3) + lambda_rel**2)
    termo_raiz = k**2 - lambda_rel**2
    if termo_raiz < -TOL: return TOL # Instável
    elif termo_raiz < 0: termo_raiz = 0

    denominador = k + math.sqrt(termo_raiz)
    if denominador <= TOL: return TOL # Instável

    kc = 1 / denominador
    return min(kc, 1.0)

# (Mantém verificar_compressao_axial_com_estabilidade - não usa k_M)
def verificar_compressao_axial_com_estabilidade(N_sd_c, A, f_c0k, f_c0d, E_005, comprimento_L, Ke_x=1.0, Ke_y=1.0, i_x=None, i_y=None, props_geom=None, beta_c=0.2):
    """Verifica ELU para compressão axial (Resistência e Estabilidade)."""
    if A is None or A <= TOL: raise ValueError(f"Área inválida ({A}).")

    passou_res, NRd_res = True, float('inf')
    passou_est, NRd_est = True, float('inf')
    lambda_x, lambda_y = 0.0, 0.0
    lambda_rel_x, lambda_rel_y = 0.0, 0.0
    kc_x, kc_y = 1.0, 1.0
    esbeltez_ok = True

    if f_c0d is None or f_c0d <= TOL:
        passou_res = abs(N_sd_c) < TOL
        NRd_res = 0.0
    else:
        NRd_res = f_c0d * A
        passou_res = abs(N_sd_c) <= NRd_res + TOL

    if N_sd_c > TOL and (f_c0d is not None and f_c0d > TOL):
        if E_005 is None or E_005 <= TOL: raise ValueError(f"E_005 inválido ({E_005}).")
        if f_c0k is None or f_c0k <= TOL: raise ValueError(f"f_c0k inválido ({f_c0k}).")

        if props_geom: i_x_calc, i_y_calc = props_geom.get('i_x'), props_geom.get('i_y')
        else: i_x_calc, i_y_calc = i_x, i_y

        if i_x_calc is None or i_y_calc is None or i_x_calc <= TOL or i_y_calc <= TOL:
            raise ValueError(f"Raios de giração inválidos (ix={i_x_calc}, iy={i_y_calc}).")

        try:
            lambda_x, lambda_rel_x = calcular_indices_esbeltez(comprimento_L, Ke_x, i_x_calc, f_c0k, E_005)
            lambda_y, lambda_rel_y = calcular_indices_esbeltez(comprimento_L, Ke_y, i_y_calc, f_c0k, E_005)
            kc_x = calcular_coeficiente_reducao_kc(lambda_rel_x, beta_c)
            kc_y = calcular_coeficiente_reducao_kc(lambda_rel_y, beta_c)
        except ValueError as e: raise ValueError(f"Erro no cálculo da estabilidade: {e}") from e

        kc_min = min(kc_x, kc_y)
        lambda_max = max(lambda_x, lambda_y)
        esbeltez_ok = lambda_max <= 140.0 + TOL
        NRd_est = kc_min * f_c0d * A
        passou_est = abs(N_sd_c) <= NRd_est + TOL

    passou_geral = passou_res and passou_est and esbeltez_ok

    return (
        passou_geral, abs(N_sd_c),
        passou_res, NRd_res,
        passou_est, NRd_est,
        lambda_x, lambda_y, lambda_rel_x, lambda_rel_y,
        kc_x, kc_y,
        esbeltez_ok
    )


def verificar_flexocompressao_resistencia(N_sd_c, M_sdx, M_sdy, A, Wx, Wy, f_c0d, f_md, k_M): # <-- k_M como parâmetro
    """Verifica ELU para flexocompressão (Resistência da Seção - Item 6.3.7), usando k_M fornecido."""
    if A <= TOL or Wx <= TOL or Wy <= TOL: return False, float('inf')
    if f_c0d <= TOL or f_md <= TOL:
        passa_sem_resistencia = (abs(N_sd_c) < TOL and abs(M_sdx) < TOL and abs(M_sdy) < TOL)
        return passa_sem_resistencia, 0.0

    sigma_Ncd = abs(N_sd_c) / A if A > TOL else 0.0
    sigma_Msdx = abs(M_sdx) / Wx if Wx > TOL else 0.0
    sigma_Msdy = abs(M_sdy) / Wy if Wy > TOL else 0.0

    termo_comp_quad = (sigma_Ncd / f_c0d)**2 if f_c0d > TOL else float('inf')
    termo_flex_x = sigma_Msdx / f_md if f_md > TOL else float('inf')
    termo_flex_y = sigma_Msdy / f_md if f_md > TOL else float('inf')

    ratio1 = termo_comp_quad + termo_flex_x + k_M * termo_flex_y
    ratio2 = termo_comp_quad + k_M * termo_flex_x + termo_flex_y
    ratio_max = max(ratio1, ratio2)

    passou = ratio_max <= 1.0 + TOL
    return passou, ratio_max

# ========= FUNÇÃO MODIFICADA PARA RETORNAR MAIS DETALHES =========
def verificar_flexocompressao_com_estabilidade(N_sd_c, M_sdx, M_sdy, A, Wx, Wy, f_c0k, f_c0d, f_md, E_005, comprimento_L, Ke_x, Ke_y, props_geom, beta_c, k_M): # <-- k_M como parâmetro
    """
    Verifica ELU para flexocompressão (Estabilidade - Item 6.5.5), usando k_M fornecido.
    RETORNA 11 VALORES: passou_geral, ratio_max, lambda_x, lambda_y, lambda_rel_x, lambda_rel_y, k_cx, k_cy, lambda_max, esbeltez_ok, passou_ratio_apenas
    """
    lambda_x, lambda_y = 0.0, 0.0
    lambda_rel_x, lambda_rel_y = 0.0, 0.0
    k_cx, k_cy = 1.0, 1.0
    ratio_max = 0.0
    lambda_max_calc = 0.0
    esbeltez_ok = True
    passou_ratio_apenas = True

    if A <= TOL or Wx <= TOL or Wy <= TOL:
        return False, float('inf'), lambda_x, lambda_y, lambda_rel_x, lambda_rel_y, k_cx, k_cy, lambda_max_calc, False, False

    passa_sem_resistencia = (abs(N_sd_c) < TOL and abs(M_sdx) < TOL and abs(M_sdy) < TOL)
    if f_c0d <= TOL or f_md <= TOL:
        return passa_sem_resistencia, ratio_max, lambda_x, lambda_y, lambda_rel_x, lambda_rel_y, k_cx, k_cy, lambda_max_calc, True, True

    if E_005 is None or E_005 <= TOL: raise ValueError(f"E_005 inválido ({E_005}).")
    if f_c0k is None or f_c0k <= TOL: raise ValueError(f"f_c0k inválido ({f_c0k}).")

    if props_geom:
        i_x_calc = props_geom.get('i_x')
        i_y_calc = props_geom.get('i_y')
    else:
        raise ValueError("props_geom são necessários.")

    if i_x_calc is None or i_y_calc is None or i_x_calc <= TOL or i_y_calc <= TOL:
        raise ValueError(f"Raios de giração inválidos (ix={i_x_calc}, iy={i_y_calc}).")

    try:
        lambda_x, lambda_rel_x = calcular_indices_esbeltez(comprimento_L, Ke_x, i_x_calc, f_c0k, E_005)
        lambda_y, lambda_rel_y = calcular_indices_esbeltez(comprimento_L, Ke_y, i_y_calc, f_c0k, E_005)
        k_cx = calcular_coeficiente_reducao_kc(lambda_rel_x, beta_c)
        k_cy = calcular_coeficiente_reducao_kc(lambda_rel_y, beta_c)
        lambda_max_calc = max(lambda_x, lambda_y)
    except ValueError as e:
        raise ValueError(f"Erro no cálculo da estabilidade para flexocompressão: {e}") from e

    esbeltez_ok = lambda_max_calc <= 140.0 + TOL
    if not esbeltez_ok:
        return False, float('inf'), lambda_x, lambda_y, lambda_rel_x, lambda_rel_y, k_cx, k_cy, lambda_max_calc, False, False

    sigma_Ncd = abs(N_sd_c) / A if A > TOL else 0.0
    sigma_Msdx = abs(M_sdx) / Wx if Wx > TOL else 0.0
    sigma_Msdy = abs(M_sdy) / Wy if Wy > TOL else 0.0

    termo_N_kx = sigma_Ncd / (k_cx * f_c0d) if abs(k_cx * f_c0d) > TOL else float('inf')
    termo_N_ky = sigma_Ncd / (k_cy * f_c0d) if abs(k_cy * f_c0d) > TOL else float('inf')
    termo_Mx_fmd = sigma_Msdx / f_md if f_md > TOL else float('inf')
    termo_My_fmd = sigma_Msdy / f_md if f_md > TOL else float('inf')

    ratio1 = termo_N_kx + termo_Mx_fmd + k_M * termo_My_fmd
    ratio2 = termo_N_ky + k_M * termo_Mx_fmd + termo_My_fmd
    ratio_max = max(ratio1, ratio2)

    passou_ratio_apenas = ratio_max <= 1.0 + TOL
    passou_geral = passou_ratio_apenas # Passa se ratio <= 1 (esbeltez já verificada)

    return passou_geral, ratio_max, lambda_x, lambda_y, lambda_rel_x, lambda_rel_y, k_cx, k_cy, lambda_max_calc, esbeltez_ok, passou_ratio_apenas

# --------------------------------------------------------------------------
# Verificar Dimensões Mínimas (Item 9.2.1)
# --------------------------------------------------------------------------
# (Mantém verificar_dimensoes_minimas)
def verificar_dimensoes_minimas(largura_b, altura_h, tipo_peca="principal_isolada"):
    """Verifica se a seção atende às dimensões mínimas da NBR 7190."""
    if largura_b <= TOL or altura_h <= TOL:
        raise ValueError(f"Dimensões b ({largura_b}) e h ({altura_h}) devem ser positivas.")

    area_mm2 = largura_b * altura_h
    espessura_min_mm = min(largura_b, altura_h)

    if tipo_peca == "principal_isolada": area_min_mm2, espessura_min_req_mm = 5000, 50
    elif tipo_peca == "secundaria_isolada": area_min_mm2, espessura_min_req_mm = 1800, 25
    elif tipo_peca == "principal_multipla": area_min_mm2, espessura_min_req_mm = 3500, 25
    elif tipo_peca == "secundaria_multipla": area_min_mm2, espessura_min_req_mm = 1800, 18
    else: area_min_mm2, espessura_min_req_mm = 5000, 50

    area_ok = area_mm2 >= area_min_mm2 - TOL
    espessura_ok = espessura_min_mm >= espessura_min_req_mm - TOL
    return area_ok, espessura_ok

# --------------------------------------------------------------------------
# Verificação de Estabilidade Lateral de Vigas (Item 6.5.6)
# --------------------------------------------------------------------------
# (Mantém beta_M_tabela, obter_beta_M, verificar_estabilidade_lateral_viga)
beta_M_tabela = {
    1: 6.0, 2: 8.8, 3: 12.3, 4: 15.9, 5: 19.5, 6: 23.1, 7: 26.7, 8: 30.3,
    9: 34.0, 10: 37.6, 11: 41.2, 12: 44.8, 13: 48.5, 14: 52.1, 15: 55.8,
    16: 59.4, 17: 63.0, 18: 66.7, 19: 70.3, 20: 74.0
}

def obter_beta_M(h_b_ratio):
    """Obtém beta_M da Tabela 8 por interpolação linear."""
    if h_b_ratio is None or h_b_ratio <= TOL: return None
    if h_b_ratio < 1.0: return beta_M_tabela[1]
    if h_b_ratio > 20.0: return beta_M_tabela[20]

    h_b_inf = math.floor(h_b_ratio)
    h_b_sup = math.ceil(h_b_ratio)

    if abs(h_b_inf - h_b_ratio) < TOL and h_b_inf in beta_M_tabela:
        return beta_M_tabela[h_b_inf]

    beta_M_inf = beta_M_tabela.get(h_b_inf)
    beta_M_sup = beta_M_tabela.get(h_b_sup)

    if beta_M_inf is None or beta_M_sup is None:
        return beta_M_tabela.get(round(h_b_ratio)) or beta_M_tabela[20]

    beta_M = beta_M_inf + (beta_M_sup - beta_M_inf) * (h_b_ratio - h_b_inf)
    return beta_M

def verificar_estabilidade_lateral_viga(largura_b, altura_h, L1, E0_med, f_md, k_mod, M_sdx, Wx):
    """Verifica a estabilidade lateral de vigas retangulares (Item 6.5.6)."""
    resultados_fl = {
        'verificacao_aplicavel': False, 'dispensado': False, 'passou': None,
        'h_b_ratio': None, 'L1_b': None, 'limite_dispensacao': None,
        'beta_M': None, 'E0_ef': None, 'sigma_cd_atuante': None,
        'sigma_cd_max_adm': None, 'mensagem': ''
    }
    if abs(M_sdx) < TOL:
         resultados_fl['mensagem'] = "Não aplicável (Momento Msdx ≈ 0)."
         resultados_fl['passou'] = True
         return resultados_fl
    if largura_b <= TOL or altura_h <= TOL or L1 < 0 or E0_med <= TOL or f_md <= TOL or abs(k_mod) < TOL or Wx <= TOL:
        resultados_fl['mensagem'] = f"Erro: Inputs inválidos (b={largura_b:.1f}, h={altura_h:.1f}, L1={L1:.0f}, E0_med={E0_med:.0f}, f_md={f_md:.2f}, k_mod={k_mod:.2f}, Wx={Wx:.0f})."
        resultados_fl['passou'] = False
        return resultados_fl

    resultados_fl['verificacao_aplicavel'] = True
    try:
        h_b_ratio = altura_h / largura_b
        resultados_fl['h_b_ratio'] = h_b_ratio
        beta_M = obter_beta_M(h_b_ratio)
        if beta_M is None: raise ValueError(f"Não foi possível obter beta_M para h/b = {h_b_ratio:.2f}")
        resultados_fl['beta_M'] = beta_M
        E0_ef = obter_E0_ef({'E_0med': E0_med}, k_mod)
        resultados_fl['E0_ef'] = E0_ef

        if L1 < TOL:
            resultados_fl['L1_b'] = 0.0
            resultados_fl['limite_dispensacao'] = float('inf')
            resultados_fl['dispensado'] = True
            resultados_fl['passou'] = True
            resultados_fl['mensagem'] = f"Dispensado (L1 = {L1:.0f} mm)."
            return resultados_fl

        L1_b = L1 / largura_b
        resultados_fl['L1_b'] = L1_b
        denominador_lim_disp = beta_M * f_md
        if abs(denominador_lim_disp) < TOL: limite_dispensacao = float('inf')
        else: limite_dispensacao = E0_ef / denominador_lim_disp
        resultados_fl['limite_dispensacao'] = limite_dispensacao

        if L1_b <= limite_dispensacao + TOL:
             resultados_fl['dispensado'] = True
             resultados_fl['passou'] = True
             resultados_fl['mensagem'] = f"Dispensado (L1/b = {L1_b:.2f} <= Limite = {limite_dispensacao:.2f})."
        else:
            resultados_fl['dispensado'] = False
            resultados_fl['mensagem'] = f"Necessária (L1/b = {L1_b:.2f} > Limite = {limite_dispensacao:.2f}). "
            sigma_cd_atuante = abs(M_sdx) / Wx
            resultados_fl['sigma_cd_atuante'] = sigma_cd_atuante
            denominador_lim_sigma = L1_b * beta_M
            if abs(denominador_lim_sigma) < TOL: sigma_cd_max_adm = float('inf')
            else: sigma_cd_max_adm = E0_ef / denominador_lim_sigma
            resultados_fl['sigma_cd_max_adm'] = sigma_cd_max_adm
            passou_alt = sigma_cd_atuante <= sigma_cd_max_adm + TOL
            resultados_fl['passou'] = passou_alt
            if passou_alt: resultados_fl['mensagem'] += f"Alternativa OK (σ = {sigma_cd_atuante:.2f} <= Lim = {sigma_cd_max_adm:.2f} MPa)."
            else: resultados_fl['mensagem'] += f"Alternativa NÃO OK (σ = {sigma_cd_atuante:.2f} > Lim = {sigma_cd_max_adm:.2f} MPa)."

    except (ValueError, KeyError, TypeError, ZeroDivisionError) as e:
        resultados_fl['passou'] = False
        resultados_fl['mensagem'] = f"Erro cálculo FL: {str(e)}"
    except Exception as e:
        resultados_fl['passou'] = False
        resultados_fl['mensagem'] = f"Erro inesperado FL: {type(e).__name__} - {str(e)}"

    return resultados_fl